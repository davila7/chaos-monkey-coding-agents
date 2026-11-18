"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
CHUNK = 1024 * 1024


class Response(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


class Transport(Protocol):
    def send(self, method: str, path: str, headers: dict[str, str], body: bytes | dict[str, Any] | None) -> Response:
        """Sends one request and returns the response. A dict body is sent as JSON, bytes as they are."""

    def now(self) -> float:
        """The current Unix time in seconds."""


@dataclass(frozen=True)
class Session:
    upload_id: str
    chunk_size: int
    expires_at: int  # Unix time in seconds


@dataclass(frozen=True)
class StoredFile:
    file_id: str
    name: str
    size: int
    checksum: str


class ApiError(Exception):
    """An error response: its HTTP status and the error code from its body."""

    def __init__(self, status: int, code: str):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        missing: list[int] = []
        try:
            missing = [int(x) for x in json.loads(r.body)["error"].get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        raise _Detail(r.status, code, missing)
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def upload_file(
    transport: Transport,
    name: str,
    data: bytes,
    plan: str,
    session: Session | None = None,
    record: Callable[[Session], None] | None = None,
) -> StoredFile:
    """Uploads `data` as the file `name` and returns the stored file.

    `plan` is the account's plan as our account records hold it. `session` is a session saved from
    an earlier call for the same name and data that did not finish, or None; it is resumed when that
    is allowed. `record`, when given, is called with every session this call starts, before its first
    part is sent. Raises ApiError when the API answers with an error that ends the upload.
    """
    chunk = _chunk_size(plan, len(data))
    resumed = session is not None and session.expires_at - transport.now() > RESUME_MARGIN
    replaced = False
    current = session if resumed else None
    etags: dict[int, str] = {}
    local = _parts(data, session.chunk_size if resumed else chunk)

    while True:
        try:
            if current is None:
                current = _start(transport, name, len(data), chunk, record)
                local = _parts(data, current.chunk_size)
                etags = {}
                todo = list(range(1, len(local) + 1))
            elif resumed:
                resumed = False
                todo = _resume(transport, current, local, etags)
            else:
                todo = []
            base = f"{BASE}/uploads/{current.upload_id}"
            for n in todo:
                etags[n] = _send_part(transport, base, n, local[n - 1])
            commit = {
                "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(local) + 1)],
                "checksum": _file_checksum(local),
            }
            try:
                return _stored(_call(transport, "POST", f"{base}/commit", commit))
            except _Detail as e:
                if e.code != "parts_missing" or e.status != 409:
                    raise ApiError(e.status, e.code) from None
                missing = sorted(e.missing)
            for n in missing:
                etags[n] = _send_part(transport, base, n, local[n - 1])
            commit["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(local) + 1)]
            try:
                return _stored(_call(transport, "POST", f"{base}/commit", commit))
            except _Detail as e:
                raise ApiError(e.status, e.code) from None
        except _Detail as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced, current, resumed = True, None, False
                continue
            raise ApiError(e.status, e.code) from None


RESUME_MARGIN = 600
KIB = 1024
_PLANS = {  # smallest chunk, largest chunk
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}


class _Detail(ApiError):
    def __init__(self, status: int, code: str, missing: list[int]):
        super().__init__(status, code)
        self.missing = missing


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _PLANS[key]
    if size >= hi:
        return hi
    need = -(-size // (64 * KIB)) * 64 * KIB
    return max(lo, need)


def _parts(data: bytes, chunk: int) -> list[bytes]:
    return [data[o : o + chunk] for o in range(0, len(data), chunk)]


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    h = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).digest()
    return base64.urlsafe_b64encode(h).decode().rstrip("=") + f"-{len(parts)}"


def _start(transport: Transport, name: str, size: int, chunk: int, record: Callable[[Session], None] | None) -> Session:
    s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk})
    started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
    if record is not None:
        record(started)
    return started


def _send_part(transport: Transport, base: str, n: int, part: bytes) -> str:
    r = _call(transport, "PUT", f"{base}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
    return r["etag"]


def _resume(transport: Transport, session: Session, local: list[bytes], etags: dict[int, str]) -> list[int]:
    try:
        r = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
    except _Detail as e:
        if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
            raise _Detail(410, "upload_expired", []) from None
        raise
    held = {p["part"]: p for p in r["parts"]}
    todo = []
    for n, part in enumerate(local, 1):
        h = held.get(n)
        if h is not None and h["size"] == len(part) and h["checksum"] == _part_checksum(part):
            etags[n] = h["etag"]
        else:
            todo.append(n)
    return todo

"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
_UNIT = 64 * 1024
_KIB = 1024
_MIB = 1024 * _KIB
_PLANS = {
    "free": (64 * _KIB, 256 * _KIB),
    "team": (64 * _KIB, 512 * _KIB),
    "business": (256 * _KIB, 2 * _MIB),
}


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
        self.missing: list[int] = []


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
        except (ValueError, KeyError, TypeError):
            err, code = {}, ""
        exc = ApiError(r.status, code)
        try:
            exc.missing = [int(x) for x in err.get("missing", [])]
        except (AttributeError, TypeError, ValueError):
            pass
        raise exc
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
    replaced = False
    current = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at - transport.now() > 600:
        current = session
        try:
            got = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
        except ApiError as e:
            if (e.status, e.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            current = None
            replaced = True
        else:
            local = _parts(data, session.chunk_size)
            for p in got["parts"]:
                n = p["part"]
                if 1 <= n <= len(local) and p["size"] == len(local[n - 1]) and p["checksum"] == _part_checksum(local[n - 1]):
                    etags[n] = p["etag"]
    while True:
        fresh = current is None
        if fresh:
            etags = {}
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
            current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            if record is not None:
                record(current)
        try:
            return _finish(transport, current, data, etags)
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
                current = None
                continue
            raise


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _PLANS[key]
    if size >= hi:
        return hi
    need = -(-size // _UNIT) * _UNIT
    return max(lo, need)


def _parts(data: bytes, chunk: int) -> list[bytes]:
    return [data[o : o + chunk] for o in range(0, len(data), chunk)]


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


def _send_part(transport: Transport, up: Session, n: int, part: bytes) -> str:
    r = _call(transport, "PUT", f"{BASE}/uploads/{up.upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
    return r["etag"]


def _finish(transport: Transport, up: Session, data: bytes, etags: dict[int, str]) -> StoredFile:
    parts = _parts(data, up.chunk_size)
    for n, part in enumerate(parts, 1):
        if n not in etags:
            etags[n] = _send_part(transport, up, n, part)
    body = {
        "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
        "checksum": _file_checksum(parts),
    }
    path = f"{BASE}/uploads/{up.upload_id}/commit"
    try:
        return _stored(_call(transport, "POST", path, body))
    except ApiError as e:
        if not (e.status == 409 and e.code == "parts_missing"):
            raise
        missing = e.missing
    for n in sorted(missing):
        etags[n] = _send_part(transport, up, n, parts[n - 1])
    body["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
    return _stored(_call(transport, "POST", path, body))

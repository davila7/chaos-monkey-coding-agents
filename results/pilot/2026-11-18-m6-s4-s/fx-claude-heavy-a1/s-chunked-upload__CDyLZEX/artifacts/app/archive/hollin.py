"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
MIB = 1024 * KIB
GIB = 1024 * MIB
UNIT = 64 * KIB
RESUME_MARGIN = 600

# plan -> (smallest chunk, largest chunk, largest file)
PLANS = {
    "free": (64 * KIB, 256 * KIB, 4 * MIB),
    "team": (64 * KIB, 512 * KIB, 64 * MIB),
    "business": (256 * KIB, 2 * MIB, GIB),
}
PLANS["pro"] = PLANS["team"]  # renamed team on 2026-07-01


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
        code = ""
        missing: list[int] = []
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            missing = [int(n) for n in error.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        err = ApiError(r.status, code)
        err.missing = missing  # type: ignore[attr-defined]
        raise err
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode("ascii")


def _file_checksum(parts: list[bytes]) -> str:
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    top = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode("ascii").rstrip("=")
    return f"{top}-{len(parts)}"


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest, _ = PLANS[plan.strip().lower()]
    if size >= largest:
        return largest
    fit = -(-size // UNIT) * UNIT
    return max(fit, smallest)


def _is_expired(e: ApiError) -> bool:
    return e.status == 410 and e.code == "upload_expired"


def _send_parts(transport: Transport, upload_id: str, parts: list[bytes], numbers: list[int], etags: dict[int, str]) -> None:
    for n in numbers:
        part = parts[n - 1]
        r = _call(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
        etags[n] = r["etag"]


def _commit(transport: Transport, upload_id: str, parts: list[bytes], etags: dict[int, str]) -> StoredFile:
    """Commits the session; after one parts_missing, sends the missing parts and commits once more."""
    body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": _file_checksum(parts)}
    try:
        return _stored(_call(transport, "POST", f"{BASE}/uploads/{upload_id}/commit", body))
    except ApiError as e:
        if not (e.status == 409 and e.code == "parts_missing"):
            raise
        missing = sorted({n for n in e.missing if 1 <= n <= len(parts)})  # type: ignore[attr-defined]
    _send_parts(transport, upload_id, parts, missing, etags)
    body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": _file_checksum(parts)}
    return _stored(_call(transport, "POST", f"{BASE}/uploads/{upload_id}/commit", body))


def _split(data: bytes, chunk_size: int) -> list[bytes]:
    return [data[o : o + chunk_size] for o in range(0, len(data), chunk_size)]


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
    replaced = False
    resume = session is not None and session.expires_at > transport.now() + RESUME_MARGIN
    while True:
        in_session = False
        try:
            if resume:
                assert session is not None
                in_session = True
                parts = _split(data, session.chunk_size)
                upload_id = session.upload_id
                etags: dict[int, str] = {}
                try:
                    listed = _call(transport, "GET", f"{BASE}/uploads/{upload_id}/parts")
                except ApiError as e:
                    if e.status == 404 and e.code == "not_found":
                        raise ApiError(410, "upload_expired") from e
                    raise
                held = {p["part"]: p for p in listed.get("parts", [])}
                todo = []
                for n, part in enumerate(parts, 1):
                    h = held.get(n)
                    if h is not None and h["size"] == len(part) and h["checksum"] == _part_checksum(part):
                        etags[n] = h["etag"]
                    else:
                        todo.append(n)
            else:
                chunk = _chunk_size(plan, len(data))
                s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
                started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
                in_session = True
                if record is not None:
                    record(started)
                parts = _split(data, started.chunk_size)
                upload_id = started.upload_id
                etags = {}
                todo = list(range(1, len(parts) + 1))
            _send_parts(transport, upload_id, parts, todo, etags)
            return _commit(transport, upload_id, parts, etags)
        except ApiError as e:
            if not (in_session and _is_expired(e)) or replaced:
                raise
            replaced = True
            resume = False



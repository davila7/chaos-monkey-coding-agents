"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
UNIT = 64 * 1024
RESUME_MARGIN = 600
PLANS = {
    "free": (64 * 1024, 256 * 1024),
    "team": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
}
PLAN_ALIASES = {"pro": "team"}


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
        missing: list[int] = []
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            missing = [int(number) for number in error.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            code = ""
        failure = ApiError(r.status, code)
        failure.missing = missing
        raise failure
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
    chunk_size = _chunk_size(plan, len(data))
    replaced = False
    current = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at > transport.now() + RESUME_MARGIN:
        current = session
        try:
            etags = _received(transport, session, data)
        except ApiError as error:
            if (error.status, error.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            current = None
            replaced = True
    while True:
        if current is None:
            current, etags = _start(transport, name, data, chunk_size, record), {}
        try:
            return _finish(transport, current, data, etags)
        except ApiError as error:
            if error.status == 410 and error.code == "upload_expired" and not replaced:
                replaced = True
                current = None
                continue
            raise


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLANS[PLAN_ALIASES.get(plan.strip().lower(), plan.strip().lower())]
    if size >= largest:
        return largest
    needed = -(-size // UNIT) * UNIT
    return max(smallest, needed)


def _start(transport: Transport, name: str, data: bytes, chunk_size: int, record: Callable[[Session], None] | None) -> Session:
    s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk_size})
    started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
    if record is not None:
        record(started)
    return started


def _parts(data: bytes, chunk_size: int) -> list[bytes]:
    return [data[offset : offset + chunk_size] for offset in range(0, len(data), chunk_size)]


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(part).digest() for part in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


def _received(transport: Transport, session: Session, data: bytes) -> dict[int, str]:
    parts = _parts(data, session.chunk_size)
    listed = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
    etags: dict[int, str] = {}
    for held in listed["parts"]:
        number = held["part"]
        if 1 <= number <= len(parts):
            local = parts[number - 1]
            if held["size"] == len(local) and held["checksum"] == _part_checksum(local):
                etags[number] = held["etag"]
    return etags


def _send_part(transport: Transport, session: Session, number: int, part: bytes) -> str:
    sent = _call(transport, "PUT", f"{BASE}/uploads/{session.upload_id}/parts/{number}", part, {"Part-Checksum": _part_checksum(part)})
    return sent["etag"]


def _finish(transport: Transport, session: Session, data: bytes, etags: dict[int, str]) -> StoredFile:
    parts = _parts(data, session.chunk_size)
    etags = dict(etags)
    for number, part in enumerate(parts, 1):
        if number not in etags:
            etags[number] = _send_part(transport, session, number, part)
    commit = {
        "parts": [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)],
        "checksum": _file_checksum(parts),
    }
    path = f"{BASE}/uploads/{session.upload_id}/commit"
    try:
        return _stored(_call(transport, "POST", path, commit))
    except ApiError as error:
        if (error.status, error.code) != (409, "parts_missing"):
            raise
        missing = getattr(error, "missing", [])
    for number in sorted(missing):
        etags[number] = _send_part(transport, session, number, parts[number - 1])
    commit["parts"] = [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)]
    return _stored(_call(transport, "POST", path, commit))

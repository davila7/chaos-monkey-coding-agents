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
    "pro": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
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

    def __init__(self, status: int, code: str, missing: list[int] | None = None):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code
        self.missing = missing or []


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        code = ""
        missing = []
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            missing = [int(number) for number in error.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        raise ApiError(r.status, code, missing)
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
    current = None
    replaced = False
    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        current = session
        parts = _split(data, session.chunk_size)
        try:
            listed = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")["parts"]
        except ApiError as error:
            if (error.status, error.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            current = None
            replaced = True
            parts = _split(data, chunk_size)
            etags: dict[int, str] = {}
        else:
            etags = {}
            for held in listed:
                number = held["part"]
                if 1 <= number <= len(parts) and held["size"] == len(parts[number - 1]) and held["checksum"] == _part_checksum(parts[number - 1]):
                    etags[number] = held["etag"]
    else:
        etags = {}

    while True:
        if current is None:
            started = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk_size})
            current = Session(started["upload_id"], started["chunk_size"], started["expires_at"])
            parts = _split(data, current.chunk_size)
            etags = {}
            if record is not None:
                record(current)
        try:
            return _send_and_commit(transport, current, parts, etags)
        except ApiError as error:
            if error.status == 410 and error.code == "upload_expired" and not replaced:
                replaced = True
                current = None
                continue
            raise


def _split(data: bytes, chunk_size: int) -> list[bytes]:
    return [data[offset : offset + chunk_size] for offset in range(0, len(data), chunk_size)]


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLANS[plan.strip().lower()]
    if size >= largest:
        return largest
    needed = -(-size // UNIT) * UNIT
    return max(smallest, needed)


def _send_part(transport: Transport, session: Session, parts: list[bytes], number: int, etags: dict[int, str]) -> None:
    part = parts[number - 1]
    sent = _call(transport, "PUT", f"{BASE}/uploads/{session.upload_id}/parts/{number}", part, {"Part-Checksum": _part_checksum(part)})
    etags[number] = sent["etag"]


def _send_and_commit(transport: Transport, session: Session, parts: list[bytes], etags: dict[int, str]) -> StoredFile:
    for number in range(1, len(parts) + 1):
        if number not in etags:
            _send_part(transport, session, parts, number, etags)
    digests = b"".join(hashlib.sha256(part).digest() for part in parts)
    checksum = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=") + f"-{len(parts)}"
    for attempt in range(2):
        commit = {"parts": [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)], "checksum": checksum}
        try:
            return _stored(_call(transport, "POST", f"{BASE}/uploads/{session.upload_id}/commit", commit))
        except ApiError as error:
            if attempt == 1 or error.status != 409 or error.code != "parts_missing":
                raise
            missing = error.missing
        for number in sorted(missing):
            _send_part(transport, session, parts, number, etags)
    raise AssertionError

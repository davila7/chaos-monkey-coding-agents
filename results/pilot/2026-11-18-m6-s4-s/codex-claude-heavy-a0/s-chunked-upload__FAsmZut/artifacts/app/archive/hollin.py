"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
UNIT = 64 * 1024
_PLANS = {
    "free": (UNIT, 256 * 1024),
    "team": (UNIT, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
}


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


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


class _Expired(Exception):
    pass


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        error: Any = {}
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        failure = ApiError(r.status, code)
        failure.missing = error.get("missing", []) if isinstance(error, dict) else []  # type: ignore[attr-defined]
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
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    smallest, largest = _PLANS[key]
    if len(data) >= largest:
        chunk = largest
    else:
        chunk = max(smallest, -(-len(data) // UNIT) * UNIT)

    replaced = False
    resume = session
    if resume is not None and not resume.expires_at > transport.now() + 600:
        resume = None
    while True:
        try:
            return _run(transport, name, data, chunk, resume, record)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired")
            replaced = True
            resume = None


def _checks(data: bytes, size: int) -> list[bytes]:
    return [data[offset : offset + size] for offset in range(0, len(data), size)]


def _run(transport: Transport, name: str, data: bytes, chunk: int, resume: Session | None, record: Callable[[Session], None] | None) -> StoredFile:
    def guarded(method: str, path: str, body: Any = None, headers: dict[str, str] | None = None) -> Any:
        try:
            return _call(transport, method, path, body, headers)
        except ApiError as error:
            if error.status == 410 and error.code == "upload_expired":
                raise _Expired() from error
            raise

    etags: dict[int, str] = {}
    active = resume
    if active is not None:
        try:
            listing = _call(transport, "GET", f"{BASE}/uploads/{active.upload_id}/parts")
        except ApiError as error:
            if (error.status, error.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            raise _Expired() from error
        size = active.chunk_size
        parts = _checks(data, size)
        for held in listing["parts"]:
            number = held["part"]
            if 1 <= number <= len(parts):
                local = parts[number - 1]
                if held["size"] == len(local) and held["checksum"] == _part_checksum(local):
                    etags[number] = held["etag"]
    else:
        size = chunk
        parts = _checks(data, size)
        started = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": size})
        active = Session(started["upload_id"], started["chunk_size"], started["expires_at"])
        if record is not None:
            record(active)

    base = f"{BASE}/uploads/{active.upload_id}"

    def send(number: int) -> None:
        part = parts[number - 1]
        answer = guarded("PUT", f"{base}/parts/{number}", part, {"Part-Checksum": _part_checksum(part)})
        etags[number] = answer["etag"]

    for number in range(1, len(parts) + 1):
        if number not in etags:
            send(number)

    digests = b"".join(hashlib.sha256(part).digest() for part in parts)
    checksum = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).rstrip(b"=").decode() + f"-{len(parts)}"
    retried = False
    while True:
        commit = {"parts": [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)], "checksum": checksum}
        try:
            return _stored(guarded("POST", f"{base}/commit", commit))
        except ApiError as error:
            if error.status != 409 or error.code != "parts_missing" or retried:
                raise
            retried = True
            for number in sorted(error.missing):  # type: ignore[attr-defined]
                send(number)

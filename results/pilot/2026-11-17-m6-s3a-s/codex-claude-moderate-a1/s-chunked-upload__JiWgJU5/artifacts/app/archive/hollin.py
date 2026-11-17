"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"


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

    def __init__(self, status: int, code: str, details: dict[str, Any] | None = None):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code
        self.details = details or {}


def _error_object(body: bytes) -> dict[str, Any]:
    try:
        error = json.loads(body)["error"]
    except (ValueError, KeyError, TypeError):
        return {}
    return error if isinstance(error, dict) else {}


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        raise ApiError(r.status, code, _error_object(r.body))
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


KIB = 1024
PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    smallest, largest = PLANS[key]
    if size >= largest:
        return largest
    unit = 64 * KIB
    fitting = -(-size // unit) * unit
    return max(smallest, fitting)


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digests = b"".join(hashlib.sha256(part).digest() for part in parts)
    encoded = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=")
    return f"{encoded}-{len(parts)}"


class _Expired(Exception):
    pass


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
    current = session
    if current is not None and not current.expires_at > transport.now() + 600:
        current = None
    replaced = False
    while True:
        try:
            return _run(transport, name, data, plan, current, record)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired")
            replaced = True
            current = None


def _run(transport, name, data, plan, session, record):
    def guarded(*args, **kwargs):
        try:
            return _call(transport, *args, **kwargs)
        except ApiError as error:
            if error.status == 410 and error.code == "upload_expired":
                raise _Expired() from error
            raise

    etags: dict[int, str] = {}
    if session is not None:
        chunk = session.chunk_size
        parts = _split(data, chunk)
        try:
            received = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
        except ApiError as error:
            if (error.status, error.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            raise _Expired() from error
        for item in received["parts"]:
            number = item["part"]
            if 1 <= number <= len(parts) and item["size"] == len(parts[number - 1]) and item["checksum"] == _part_checksum(parts[number - 1]):
                etags[number] = item["etag"]
        started = session
    else:
        chunk = _chunk_size(plan, len(data))
        parts = _split(data, chunk)
        s = guarded("POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)

    def send(numbers):
        for number in numbers:
            part = parts[number - 1]
            result = guarded("PUT", f"{BASE}/uploads/{started.upload_id}/parts/{number}", part, {"Part-Checksum": _part_checksum(part)})
            etags[number] = result["etag"]

    send([n for n in range(1, len(parts) + 1) if n not in etags])
    commit = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": _file_checksum(parts)}
    path = f"{BASE}/uploads/{started.upload_id}/commit"
    try:
        return _stored(guarded("POST", path, commit))
    except ApiError as error:
        if (error.status, error.code) != (409, "parts_missing"):
            raise
        missing = sorted(error.details.get("missing", []))
    send(missing)
    commit["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
    return _stored(guarded("POST", path, commit))


def _split(data: bytes, chunk: int) -> list[bytes]:
    return [data[offset : offset + chunk] for offset in range(0, len(data), chunk)]

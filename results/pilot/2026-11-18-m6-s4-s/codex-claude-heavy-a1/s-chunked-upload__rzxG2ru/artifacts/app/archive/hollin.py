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
        code = ""
        missing: list[int] = []
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            missing = list(error.get("missing", []))
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        api_error = ApiError(r.status, code)
        api_error.missing = missing
        raise api_error
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


KIB = 1024
LIMITS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}
RESUME_MARGIN = 600


class _Expired(Exception):
    pass


def _limits(plan: str) -> tuple[int, int]:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    return LIMITS[key]


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = _limits(plan)
    if size >= largest:
        return largest
    fitted = -(-size // (64 * KIB)) * (64 * KIB)
    return max(smallest, fitted)


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(part).digest() for part in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


def _guard(transport: Transport, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None, expired: tuple[int, ...] = (410,)) -> Any:
    try:
        return _call(transport, method, path, body, headers)
    except ApiError as error:
        if error.status in expired and (error.status == 410 or error.code == "not_found"):
            raise _Expired() from error
        raise


def _send_part(transport: Transport, upload_id: str, number: int, part: bytes) -> str:
    result = _guard(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{number}", part, {"Part-Checksum": _part_checksum(part)})
    return result["etag"]


def _run(transport: Transport, session: Session, parts: list[bytes], resumed: bool) -> StoredFile:
    base = f"{BASE}/uploads/{session.upload_id}"
    etags: dict[int, str] = {}
    if resumed:
        listing = _guard(transport, "GET", f"{base}/parts", expired=(404, 410))
        held = {entry["part"]: entry for entry in listing["parts"]}
        for number, part in enumerate(parts, 1):
            entry = held.get(number)
            if entry and entry["size"] == len(part) and entry["checksum"] == _part_checksum(part):
                etags[number] = entry["etag"]
    for number, part in enumerate(parts, 1):
        if number not in etags:
            etags[number] = _send_part(transport, session.upload_id, number, part)
    commit = {"parts": [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)], "checksum": _file_checksum(parts)}
    try:
        return _stored(_guard(transport, "POST", f"{base}/commit", commit))
    except ApiError as error:
        if error.status != 409 or error.code != "parts_missing":
            raise
        missing = _missing(transport, error)
    for number in missing:
        etags[number] = _send_part(transport, session.upload_id, number, parts[number - 1])
    commit["parts"] = [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)]
    return _stored(_guard(transport, "POST", f"{base}/commit", commit))


def _missing(transport: Transport, error: ApiError) -> list[int]:
    return sorted(getattr(error, "missing", []))


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
    resume = session is not None and session.expires_at - transport.now() > RESUME_MARGIN
    current = session if resume else None
    while True:
        if current is None:
            chunk = _chunk_size(plan, len(data))
            started = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
            current = Session(started["upload_id"], started["chunk_size"], started["expires_at"])
            if record is not None:
                record(current)
            resumed = False
        else:
            resumed = True
        size = current.chunk_size
        parts = [data[offset : offset + size] for offset in range(0, len(data), size)]
        try:
            return _run(transport, current, parts, resumed)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired") from None
            replaced = True
            current = None

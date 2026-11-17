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


KIB = 1024
MIB = 1024 * KIB
PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2 * MIB),
}
RESUME_MARGIN = 600


class _Expired(Exception):
    pass


class _Missing(Exception):
    def __init__(self, missing: list[int]):
        super().__init__("parts_missing")
        self.missing = missing


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
        except (ValueError, KeyError, TypeError):
            error = {}
            code = ""
        if r.status == 409 and code == "parts_missing":
            missing = error.get("missing") if isinstance(error, dict) else None
            raise _Missing(sorted(missing) if isinstance(missing, list) else [])
        if r.status == 410 and code == "upload_expired":
            raise _Expired()
        raise ApiError(r.status, code)
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLANS[plan.strip().lower()]
    unit = 64 * KIB
    fitting = -(-size // unit) * unit
    return min(largest, max(smallest, fitting))


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(digests: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(digests)}"


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
    if current is not None and not current.expires_at > transport.now() + RESUME_MARGIN:
        current = None
    resumed = current is not None
    replaced = False
    while True:
        try:
            if current is None:
                current = _start(transport, name, data, plan, record)
                resumed = False
            return _run(transport, data, current, resumed)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired") from None
            replaced = True
            current = None


def _start(transport: Transport, name: str, data: bytes, plan: str, record: Callable[[Session], None] | None) -> Session:
    reply = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
    started = Session(reply["upload_id"], reply["chunk_size"], reply["expires_at"])
    if record is not None:
        record(started)
    return started


def _run(transport: Transport, data: bytes, session: Session, resumed: bool) -> StoredFile:
    base = f"{BASE}/uploads/{session.upload_id}"
    size = session.chunk_size
    parts = [data[offset : offset + size] for offset in range(0, len(data), size)]
    checksums = [_part_checksum(part) for part in parts]
    etags: dict[int, str] = {}
    if resumed:
        received = _call(transport, "GET", f"{base}/parts")
        for held in received["parts"]:
            number = held["part"]
            if 1 <= number <= len(parts) and held["size"] == len(parts[number - 1]) and held["checksum"] == checksums[number - 1]:
                etags[number] = held["etag"]

    def send(number: int) -> None:
        reply = _call(transport, "PUT", f"{base}/parts/{number}", parts[number - 1], {"Part-Checksum": checksums[number - 1]})
        etags[number] = reply["etag"]

    for number in range(1, len(parts) + 1):
        if number not in etags:
            send(number)
    digests = [hashlib.sha256(part).digest() for part in parts]
    commit = {
        "parts": [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)],
        "checksum": _file_checksum(digests),
    }
    try:
        return _stored(_call(transport, "POST", f"{base}/commit", commit))
    except _Missing as gap:
        for number in gap.missing:
            send(number)
    commit["parts"] = [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)]
    try:
        return _stored(_call(transport, "POST", f"{base}/commit", commit))
    except _Missing:
        raise ApiError(409, "parts_missing") from None

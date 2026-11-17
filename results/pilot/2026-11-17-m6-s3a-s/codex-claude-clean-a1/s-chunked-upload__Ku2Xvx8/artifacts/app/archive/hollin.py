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
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            missing = [int(n) for n in error.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            code, missing = "", []
        raised = ApiError(r.status, code)
        raised.missing = missing  # type: ignore[attr-defined]
        raise raised
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


KIB = 1024
PLAN_LIMITS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}
RESUME_MARGIN = 600


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    smallest, largest = PLAN_LIMITS[key]
    if size >= largest:
        return largest
    wanted = -(-size // (64 * KIB)) * 64 * KIB
    return max(smallest, wanted)


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode()


def _file_checksum(digests: list[bytes]) -> str:
    total = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(total).decode().rstrip("=") + f"-{len(digests)}"


def _start(transport: Transport, name: str, size: int, plan: str, record: Callable[[Session], None] | None) -> Session:
    body = {"name": name, "size": size, "chunk_size": _chunk_size(plan, size)}
    s = _call(transport, "POST", f"{BASE}/uploads", body)
    started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
    if record is not None:
        record(started)
    return started


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
    current: Session | None = None
    held: dict[int, tuple[int, str, str]] = {}
    if session is not None and session.expires_at > transport.now() + RESUME_MARGIN:
        current = session
        try:
            listing = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
            held = {p["part"]: (p["size"], p["checksum"], p["etag"]) for p in listing["parts"]}
        except ApiError as error:
            if (error.status, error.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            current = None
            held = {}
            replaced = True
    if current is None:
        current = _start(transport, name, len(data), plan, record)

    while True:
        try:
            return _run(transport, current, data, held)
        except ApiError as error:
            if (error.status, error.code) != (410, "upload_expired") or replaced:
                raise
            replaced = True
            held = {}
            current = _start(transport, name, len(data), plan, record)


def _run(transport: Transport, session: Session, data: bytes, held: dict[int, tuple[int, str, str]]) -> StoredFile:
    chunk = session.chunk_size
    parts = [data[offset : offset + chunk] for offset in range(0, len(data), chunk)]
    digests = [hashlib.sha256(part).digest() for part in parts]
    etags: dict[int, str] = {}
    base = f"{BASE}/uploads/{session.upload_id}"

    def send(number: int) -> None:
        reply = _call(transport, "PUT", f"{base}/parts/{number}", parts[number - 1], {"Part-Checksum": _part_checksum(digests[number - 1])})
        etags[number] = reply["etag"]

    for number, part in enumerate(parts, 1):
        entry = held.get(number)
        if entry is not None and entry[0] == len(part) and entry[1] == _part_checksum(digests[number - 1]):
            etags[number] = entry[2]
        else:
            send(number)

    def commit() -> StoredFile:
        body = {
            "parts": [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)],
            "checksum": _file_checksum(digests),
        }
        return _stored(_call(transport, "POST", f"{base}/commit", body))

    try:
        return commit()
    except ApiError as error:
        if (error.status, error.code) != (409, "parts_missing"):
            raise
        missing = error.missing
    for number in sorted(missing):
        send(number)
    return commit()

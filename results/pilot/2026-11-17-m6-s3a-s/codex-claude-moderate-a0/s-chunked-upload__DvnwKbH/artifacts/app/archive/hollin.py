"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
UNIT = 64 * 1024
KIB = 1024
MIB = 1024 * KIB
RESUME_MARGIN = 600
PLANS = {
    "free": (64 * KIB, 256 * KIB, 4 * MIB),
    "team": (64 * KIB, 512 * KIB, 64 * MIB),
    "business": (256 * KIB, 2 * MIB, 1024 * MIB),
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


class _PartsMissing(ApiError):
    def __init__(self, status: int, code: str, missing: list[int]):
        super().__init__(status, code)
        self.missing = missing


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            code = str(json.loads(r.body)["error"]["code"])
            missing = json.loads(r.body)["error"].get("missing") or []
        except (ValueError, KeyError, TypeError, AttributeError):
            code = ""
            missing = []
        if r.status == 409 and code == "parts_missing":
            raise _PartsMissing(r.status, code, list(missing))
        raise ApiError(r.status, code)
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
    limits = _limits(plan)
    chunk = _new_chunk_size(limits, len(data))
    replaced = False
    current = session
    resume = session is not None and session.expires_at - transport.now() > RESUME_MARGIN
    etags: dict[int, str] = {}
    to_send: list[int] = []

    while True:
        try:
            if current is None or not resume:
                current = _start(transport, name, len(data), limits, chunk, record)
                chunks = _cut(data, current.chunk_size)
                etags = {}
                to_send = list(range(1, len(chunks) + 1))
            else:
                chunks = _cut(data, current.chunk_size)
                etags = {}
                to_send = []
                listing = _call(transport, "GET", f"{BASE}/uploads/{current.upload_id}/parts")
                held = {entry["part"]: entry for entry in listing["parts"]}
                for number, part in enumerate(chunks, 1):
                    entry = held.get(number)
                    if entry is not None and entry["size"] == len(part) and entry["checksum"] == _part_checksum(part):
                        etags[number] = entry["etag"]
                    else:
                        to_send.append(number)
            resume = False
            return _send_and_commit(transport, current, data, chunks, etags, to_send)
        except ApiError as error:
            expired = error.status == 410 and error.code == "upload_expired"
            lost = resume and error.status == 404 and error.code == "not_found"
            if (expired or lost) and not replaced and (current is not None):
                replaced = True
                resume = False
                current = None
                continue
            raise


def _limits(plan: str) -> tuple[int, int, int]:
    name = plan.strip().lower()
    if name == "pro":
        name = "team"
    return PLANS[name]


def _new_chunk_size(limits: tuple[int, int, int], size: int) -> int:
    smallest, largest, _ = limits
    if size >= largest:
        return largest
    fitting = -(-size // UNIT) * UNIT
    return min(largest, max(smallest, fitting))


def _start(transport: Transport, name: str, size: int, limits: tuple[int, int, int], chunk: int, record: Callable[[Session], None] | None) -> Session:
    reply = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk})
    started = Session(reply["upload_id"], reply["chunk_size"], reply["expires_at"])
    if record is not None:
        record(started)
    return started


def _cut(data: bytes, chunk: int) -> list[bytes]:
    return [data[offset : offset + chunk] for offset in range(0, len(data), chunk)]


def _part_digest(part: bytes) -> bytes:
    return hashlib.sha256(part).digest()


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(_part_digest(part)).decode()


def _file_checksum(chunks: list[bytes]) -> str:
    joined = hashlib.sha256(b"".join(_part_digest(part) for part in chunks)).digest()
    return base64.urlsafe_b64encode(joined).decode().rstrip("=") + f"-{len(chunks)}"


def _put(transport: Transport, current: Session, number: int, part: bytes) -> str:
    reply = _call(transport, "PUT", f"{BASE}/uploads/{current.upload_id}/parts/{number}", part, {"Part-Checksum": _part_checksum(part)})
    return reply["etag"]


def _send_and_commit(transport: Transport, current: Session, data: bytes, chunks: list[bytes], etags: dict[int, str], to_send: list[int]) -> StoredFile:
    for number in to_send:
        etags[number] = _put(transport, current, number, chunks[number - 1])
    body = {
        "parts": [{"part": number, "etag": etags[number]} for number in range(1, len(chunks) + 1)],
        "checksum": _file_checksum(chunks),
    }
    path = f"{BASE}/uploads/{current.upload_id}/commit"
    try:
        return _stored(_call(transport, "POST", path, body))
    except ApiError as error:
        if not isinstance(error, _PartsMissing):
            raise
        missing = error.missing
    for number in sorted(set(missing)):
        etags[number] = _put(transport, current, number, chunks[number - 1])
    body["parts"] = [{"part": number, "etag": etags[number]} for number in range(1, len(chunks) + 1)]
    return _stored(_call(transport, "POST", path, body))

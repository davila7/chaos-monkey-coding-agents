"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
_UNIT = 64 * 1024
_PLANS = {
    "free": (64 * 1024, 256 * 1024),
    "team": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
}


def _limits(plan: str) -> tuple[int, int]:
    name = plan.strip().lower()
    return _PLANS["team" if name == "pro" else name]


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
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        error = ApiError(r.status, code)
        try:
            error.missing = [int(n) for n in json.loads(r.body)["error"]["missing"]]
        except (ValueError, KeyError, TypeError):
            error.missing = []
        raise error
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
    smallest, largest = _limits(plan)
    size = len(data)
    if size >= largest:
        chunk_size = largest
    else:
        chunk_size = max(smallest, -(-size // _UNIT) * _UNIT)

    replaced = False
    current = None
    if session is not None and session.expires_at - transport.now() > 600:
        current = session
    resumed = current is not None

    while True:
        if current is None:
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk_size})
            current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            if record is not None:
                record(current)
            resumed = False
        try:
            return _finish(transport, current, data, resumed)
        except ApiError as error:
            expired = error.status == 410 and error.code == "upload_expired"
            unknown = error.status == 404 and error.code == "not_found" and getattr(error, "from_read", False)
            if replaced or not (expired or unknown):
                raise
            replaced = True
            current = None


def _finish(transport: Transport, session: Session, data: bytes, resumed: bool) -> StoredFile:
    base = f"{BASE}/uploads/{session.upload_id}"
    size = session.chunk_size
    parts = [data[offset : offset + size] for offset in range(0, len(data), size)]
    sums = [hashlib.sha256(part).digest() for part in parts]
    etags: dict[int, str] = {}

    def send(number: int) -> None:
        part = parts[number - 1]
        header = {"Part-Checksum": "sha256=" + base64.b64encode(sums[number - 1]).decode()}
        etags[number] = _call(transport, "PUT", f"{base}/parts/{number}", part, header)["etag"]

    if resumed:
        try:
            held = _call(transport, "GET", f"{base}/parts")
        except ApiError as error:
            error.from_read = True
            raise
        for entry in held["parts"]:
            number = entry["part"]
            if (
                1 <= number <= len(parts)
                and entry["size"] == len(parts[number - 1])
                and entry["checksum"] == "sha256=" + base64.b64encode(sums[number - 1]).decode()
            ):
                etags[number] = entry["etag"]
    for number in range(1, len(parts) + 1):
        if number not in etags:
            send(number)

    digest = base64.urlsafe_b64encode(hashlib.sha256(b"".join(sums)).digest()).decode().rstrip("=")
    checksum = f"{digest}-{len(parts)}"
    for attempt in range(2):
        body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
        try:
            return _stored(_call(transport, "POST", f"{base}/commit", body))
        except ApiError as error:
            if error.status == 409 and error.code == "parts_missing" and attempt == 0:
                for number in sorted(error.missing):
                    send(number)
            else:
                raise
    raise AssertionError

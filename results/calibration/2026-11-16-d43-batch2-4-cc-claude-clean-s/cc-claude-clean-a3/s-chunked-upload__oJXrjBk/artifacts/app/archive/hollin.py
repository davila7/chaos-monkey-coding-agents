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
        self.missing: list[int] = []


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            missing = [int(n) for n in err.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            code, missing = "", []
        error = ApiError(r.status, code)
        error.missing = missing
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
    smallest, largest = _plan_chunks(plan)
    if len(data) >= largest:
        chunk = largest
    else:
        chunk = min(largest, max(smallest, -(-len(data) // _STEP) * _STEP))

    replaced = False

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        new = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(new)
        return new

    current: Session | None = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at - transport.now() > 600:
        try:
            listing = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
        except ApiError as e:
            if (e.status, e.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            replaced = True
        else:
            current = session
            local = _parts(data, session.chunk_size)
            for p in listing["parts"]:
                n = p["part"]
                if 1 <= n <= len(local) and p["size"] == len(local[n - 1]) and p["checksum"] == _part_checksum(local[n - 1]):
                    etags[n] = p["etag"]
    if current is None:
        current = start()

    while True:
        parts = _parts(data, current.chunk_size)
        try:
            for n, part in enumerate(parts, 1):
                if n not in etags:
                    etags[n] = _send_part(transport, current, n, part)
            missing_retry = False
            while True:
                body = {
                    "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
                    "checksum": _file_checksum(parts),
                }
                try:
                    return _stored(_call(transport, "POST", f"{BASE}/uploads/{current.upload_id}/commit", body))
                except ApiError as e:
                    if e.status != 409 or e.code != "parts_missing" or missing_retry:
                        raise
                    missing_retry = True
                    for n in sorted(e.missing):
                        etags[n] = _send_part(transport, current, n, parts[n - 1])
        except ApiError as e:
            if e.status != 410 or e.code != "upload_expired" or replaced:
                raise
            replaced = True
            etags = {}
            current = start()


_STEP = 64 * 1024
_PLANS = {
    "free": (64 * 1024, 256 * 1024),
    "team": (64 * 1024, 512 * 1024),
    "pro": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
}


def _plan_chunks(plan: str) -> tuple[int, int]:
    return _PLANS[plan.strip().lower()]


def _parts(data: bytes, chunk: int) -> list[bytes]:
    return [data[o : o + chunk] for o in range(0, len(data), chunk)]


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


def _send_part(transport: Transport, session: Session, n: int, part: bytes) -> str:
    r = _call(transport, "PUT", f"{BASE}/uploads/{session.upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
    return r["etag"]

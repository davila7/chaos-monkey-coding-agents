"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
MIB = 1024 * KIB
# plan -> (smallest chunk, largest chunk)
PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2 * MIB),
}
RESUME_MARGIN = 600


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
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            missing = [int(n) for n in err.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            code = ""
        error = ApiError(r.status, code)
        error.missing = missing  # type: ignore[attr-defined]
        raise error
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


class _Expired(Exception):
    pass


def _call_s(transport: Transport, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None) -> Any:
    """Like _call, but an expired session is reported as _Expired."""
    try:
        return _call(transport, method, path, body, headers)
    except ApiError as e:
        if e.status == 410 and e.code == "upload_expired":
            raise _Expired() from e
        raise


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    enc = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=")
    return f"{enc}-{len(parts)}"


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLANS[plan.strip().lower()]
    if size >= largest:
        return largest
    unit = 64 * KIB
    return max(smallest, -(-size // unit) * unit)


def _send_part(transport: Transport, upload_id: str, n: int, part: bytes) -> str:
    r = _call_s(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
    return r["etag"]


def _run(transport: Transport, upload_id: str, parts: list[bytes], etags: dict[int, str], checksum: str, name: str) -> StoredFile:
    """Sends the parts not in `etags` and commits. `etags` maps part number to etag."""
    for n, part in enumerate(parts, 1):
        if n not in etags:
            etags[n] = _send_part(transport, upload_id, n, part)
    missing_retry = False
    while True:
        body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
        try:
            return _stored(_call_s(transport, "POST", f"{BASE}/uploads/{upload_id}/commit", body))
        except ApiError as e:
            if e.status != 409 or e.code != "parts_missing" or missing_retry:
                raise
            missing_retry = True
            missing = e.missing
        for n in sorted(missing):
            etags[n] = _send_part(transport, upload_id, n, parts[n - 1])


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

    def split(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    replaced = False
    current: Session | None = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        parts = split(session.chunk_size)
        try:
            r = _call_s(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
            for p in r["parts"]:
                n = p["part"]
                if 1 <= n <= len(parts) and p["size"] == len(parts[n - 1]) and p["checksum"] == _part_checksum(parts[n - 1]):
                    etags[n] = p["etag"]
            current = session
        except _Expired:
            replaced = True
        except ApiError as e:
            if e.status != 404 or e.code != "not_found":
                raise
            replaced = True
    while True:
        if current is None:
            current = start()
            parts = split(current.chunk_size)
            etags = {}
        try:
            return _run(transport, current.upload_id, parts, etags, _file_checksum(parts), name)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired") from None
            replaced = True
            current = None

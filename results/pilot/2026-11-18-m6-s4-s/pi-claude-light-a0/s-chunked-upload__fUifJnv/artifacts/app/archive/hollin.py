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
        code, missing = "", []
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            missing = list(error.get("missing") or [])
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        err = ApiError(r.status, code)
        err.missing = missing  # type: ignore[attr-defined]
        raise err
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
    replaced = False  # a call starts at most one replacement session
    current: Session | None = None
    if session is not None and session.expires_at - transport.now() > 600:
        current = session
        resume = True
    else:
        resume = False
    while True:
        try:
            if current is None:
                current = _start(transport, name, data, plan)
                if record is not None:
                    record(current)
                resume = False
            return _run(transport, data, current, resume)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired")
            replaced = True
            current = None
            resume = False


class _Expired(Exception):
    pass


_KIB = 1024
_LIMITS = {  # smallest chunk, largest chunk, largest file
    "free": (64 * _KIB, 256 * _KIB, 4 * 1024 * _KIB),
    "team": (64 * _KIB, 512 * _KIB, 64 * 1024 * _KIB),
    "business": (256 * _KIB, 2048 * _KIB, 1024 * 1024 * _KIB),
}


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi, _ = _LIMITS[key]
    if size >= hi:
        return hi
    fit = -(-size // (64 * _KIB)) * 64 * _KIB
    return min(hi, max(lo, fit))


def _start(transport: Transport, name: str, data: bytes, plan: str) -> Session:
    body = {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))}
    s = _call(transport, "POST", f"{BASE}/uploads", body)
    return Session(s["upload_id"], s["chunk_size"], s["expires_at"])


def _guard(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except ApiError as e:
        if e.status == 410 and e.code == "upload_expired":
            raise _Expired() from e
        raise


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _run(transport: Transport, data: bytes, s: Session, resume: bool) -> StoredFile:
    cs = s.chunk_size
    parts = [data[o : o + cs] for o in range(0, len(data), cs)]
    base = f"{BASE}/uploads/{s.upload_id}"
    etags: dict[int, str] = {}
    held: dict[int, dict[str, Any]] = {}
    if resume:
        try:
            listing = _call(transport, "GET", f"{base}/parts")
        except ApiError as e:
            if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
                raise _Expired() from e
            raise
        held = {p["part"]: p for p in listing["parts"]}

    def send(n: int) -> None:
        part = parts[n - 1]
        r = _guard(lambda: _call(transport, "PUT", f"{base}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)}))
        etags[n] = r["etag"]

    for n, part in enumerate(parts, 1):
        h = held.get(n)
        if h is not None and h["size"] == len(part) and h["checksum"] == _part_checksum(part):
            etags[n] = h["etag"]
        else:
            send(n)

    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    fsum = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=") + f"-{len(parts)}"

    def commit() -> Any:
        body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": fsum}
        return _guard(lambda: _call(transport, "POST", f"{base}/commit", body))

    try:
        return _stored(commit())
    except ApiError as e:
        if not (e.status == 409 and e.code == "parts_missing"):
            raise
        missing = sorted(getattr(e, "missing", []))
    for n in missing:
        send(n)
    return _stored(commit())

"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
_STEP = 64 * 1024
_PLANS = {
    "free": (64 * 1024, 256 * 1024),
    "team": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
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

    def __init__(self, status: int, code: str, missing: list[int] | None = None):
        super().__init__(f"{status} {code}")
        self.missing = missing or []
        self.status = status
        self.code = code


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        code, missing = "", []
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            missing = [int(x) for x in err.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        raise ApiError(r.status, code, missing)
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
    chunk = _chunk_size(plan, len(data))
    replaced = False
    if session is not None and session.expires_at > transport.now() + 600:
        current = session
        resume = True
    else:
        current = _start(transport, name, len(data), chunk, record)
        resume = False
    while True:
        try:
            return _run(transport, current, data, resume)
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
            elif resume and e.status == 404 and e.code == "not_found" and not replaced and e.args and getattr(e, "_listing", False):
                replaced = True
            else:
                raise
        current = _start(transport, name, len(data), chunk, record)
        resume = False


class _ListingError(ApiError):
    _listing = True


def _start(transport: Transport, name: str, size: int, chunk: int, record: Callable[[Session], None] | None) -> Session:
    s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk})
    started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
    if record is not None:
        record(started)
    return started


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _PLANS[key]
    fit = -(-size // _STEP) * _STEP
    return min(hi, max(lo, fit))


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode()


def _run(transport: Transport, s: Session, data: bytes, resume: bool) -> StoredFile:
    size = s.chunk_size
    parts = [data[o : o + size] for o in range(0, len(data), size)]
    digests = [hashlib.sha256(p).digest() for p in parts]
    base = f"{BASE}/uploads/{s.upload_id}"
    etags: dict[int, str] = {}
    to_send = list(range(1, len(parts) + 1))
    if resume:
        try:
            listing = _call(transport, "GET", f"{base}/parts")
        except ApiError as e:
            if e.status in (404, 410) and e.code in ("not_found", "upload_expired"):
                raise _ListingError(e.status, e.code) from None
            raise
        held = {p["part"]: p for p in listing.get("parts", [])}
        to_send = []
        for n in range(1, len(parts) + 1):
            h = held.get(n)
            if h and h["size"] == len(parts[n - 1]) and h["checksum"] == _part_checksum(digests[n - 1]):
                etags[n] = h["etag"]
            else:
                to_send.append(n)

    def send(nums: list[int]) -> None:
        for n in nums:
            r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": _part_checksum(digests[n - 1])})
            etags[n] = r["etag"]

    send(to_send)
    whole = hashlib.sha256(b"".join(digests)).digest()
    checksum = base64.urlsafe_b64encode(whole).decode().rstrip("=") + f"-{len(parts)}"
    body = lambda: {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
    try:
        return _stored(_call(transport, "POST", f"{base}/commit", body()))
    except ApiError as e:
        if not (e.status == 409 and e.code == "parts_missing"):
            raise
        missing = e.missing
    send(sorted(missing))
    return _stored(_call(transport, "POST", f"{base}/commit", body()))

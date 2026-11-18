"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
PLANS = {  # plan: (smallest chunk, largest chunk)
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
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
            missing = list(err.get("missing") or [])
        except (ValueError, KeyError, TypeError, AttributeError):
            code = ""
        exc = ApiError(r.status, code)
        exc.missing = missing  # type: ignore[attr-defined]
        raise exc
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    return f"{_b64url(hashlib.sha256(digests).digest())}-{len(parts)}"


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLANS[plan.strip().lower()]
    if size >= largest:
        return largest
    unit = 64 * KIB
    fit = -(-size // unit) * unit
    return max(smallest, fit)


class _Expired(Exception):
    pass


def _guard(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except ApiError as e:
        if e.status == 410 and e.code == "upload_expired":
            raise _Expired() from e
        raise


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
    current = session
    if current is not None and current.expires_at - transport.now() <= RESUME_MARGIN:
        current = None
    while True:
        try:
            return _run(transport, name, data, plan, current, record)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired") from None
            replaced = True
            current = None


def _run(transport: Transport, name: str, data: bytes, plan: str, saved: Session | None, record: Callable[[Session], None] | None) -> StoredFile:
    etags: dict[int, str] = {}
    sess = saved
    if sess is not None:
        try:
            listing = _call(transport, "GET", f"{BASE}/uploads/{sess.upload_id}/parts")
        except ApiError as e:
            if (e.status, e.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            sess = None
            listing = None
    if sess is None:
        chunk = _chunk_size(plan, len(data))
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        sess = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(sess)
        listing = None
    size = sess.chunk_size
    parts = [data[o : o + size] for o in range(0, len(data), size)]
    base = f"{BASE}/uploads/{sess.upload_id}"
    if listing is not None:
        for p in listing.get("parts", []):
            n = p["part"]
            if 1 <= n <= len(parts) and p["size"] == len(parts[n - 1]) and p["checksum"] == _part_checksum(parts[n - 1]):
                etags[n] = p["etag"]

    def send(n: int) -> None:
        part = parts[n - 1]
        r = _guard(lambda: _call(transport, "PUT", f"{base}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)}))
        etags[n] = r["etag"]

    for n in range(1, len(parts) + 1):
        if n not in etags:
            send(n)
    body = {"parts": [], "checksum": _file_checksum(parts)}
    retried = False
    while True:
        body["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
        try:
            return _stored(_guard(lambda: _call(transport, "POST", f"{base}/commit", body)))
        except ApiError as e:
            if e.status == 409 and e.code == "parts_missing" and not retried:
                retried = True
                for n in sorted(getattr(e, "missing", [])):
                    send(n)
                continue
            raise

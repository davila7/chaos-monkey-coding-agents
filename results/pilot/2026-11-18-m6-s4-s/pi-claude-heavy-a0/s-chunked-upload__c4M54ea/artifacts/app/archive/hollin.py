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
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
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
    state = {"replaced": False}
    sess = None
    if session is not None and session.expires_at > transport.now() + 600:
        sess = session
    resumed = sess is not None
    while True:
        try:
            if sess is None:
                sess = _start(transport, name, data, plan, record)
                resumed = False
            return _run(transport, sess, data, resumed)
        except _Expired as e:
            if state["replaced"]:
                raise ApiError(410, "upload_expired") from None
            state["replaced"] = True
            sess = None


class _Expired(Exception):
    pass


_KIB = 1024
_PLANS = {
    "free": (64 * _KIB, 256 * _KIB),
    "team": (64 * _KIB, 512 * _KIB),
    "business": (256 * _KIB, 2048 * _KIB),
}


def _chunk_for(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _PLANS[key]
    if size >= hi:
        return hi
    unit = 64 * _KIB
    c = max(-(-size // unit) * unit, lo)
    return min(c, hi)


def _start(transport: Transport, name: str, data: bytes, plan: str, record: Callable[[Session], None] | None) -> Session:
    body = {"name": name, "size": len(data), "chunk_size": _chunk_for(plan, len(data))}
    s = _call(transport, "POST", f"{BASE}/uploads", body)
    started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
    if record is not None:
        record(started)
    return started


def _req(transport: Transport, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None) -> Any:
    try:
        return _call(transport, method, path, body, headers)
    except ApiError as e:
        if e.status == 410 and e.code == "upload_expired":
            raise _Expired() from None
        raise


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _run(transport: Transport, sess: Session, data: bytes, resumed: bool) -> StoredFile:
    cs = sess.chunk_size
    parts = [data[o : o + cs] for o in range(0, len(data), cs)]
    base = f"{BASE}/uploads/{sess.upload_id}"
    etags: dict[int, str] = {}
    if resumed:
        try:
            listing = _call(transport, "GET", f"{base}/parts")
        except ApiError as e:
            if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
                raise _Expired() from None
            raise
        for h in listing["parts"]:
            n = h["part"]
            if 1 <= n <= len(parts) and h["size"] == len(parts[n - 1]) and h["checksum"] == _part_checksum(parts[n - 1]):
                etags[n] = h["etag"]

    def send(n: int) -> None:
        r = _req(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": _part_checksum(parts[n - 1])})
        etags[n] = r["etag"]

    for n in range(1, len(parts) + 1):
        if n not in etags:
            send(n)
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    fsum = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=") + f"-{len(parts)}"
    for attempt in range(2):
        commit = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": fsum}
        r = transport.send("POST", f"{base}/commit", {}, commit)
        if r.status in (200, 201):
            return _stored(json.loads(r.body))
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
        except (ValueError, KeyError, TypeError):
            err, code = {}, ""
        if r.status == 410 and code == "upload_expired":
            raise _Expired()
        if r.status == 409 and code == "parts_missing" and attempt == 0:
            for n in sorted(err.get("missing", [])):
                send(n)
            continue
        raise ApiError(r.status, code)
    raise ApiError(409, "parts_missing")

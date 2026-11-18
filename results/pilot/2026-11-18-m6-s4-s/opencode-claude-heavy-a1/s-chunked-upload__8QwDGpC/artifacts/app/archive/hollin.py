"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"


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
        err = ApiError(r.status, code)
        try:
            err.missing = [int(x) for x in json.loads(r.body)["error"].get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            err.missing = []
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
    replaced = False
    sess = None
    if session is not None and session.expires_at - transport.now() > 600:
        sess = session
        resuming = True
    else:
        resuming = False
    while True:
        try:
            if sess is None:
                sess = _start(transport, name, data, plan, record)
                resuming = False
            return _run(transport, data, sess, resuming)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired")
            replaced = True
            sess = None
            resuming = False


class _Expired(Exception):
    pass


_KIB = 1024
_LIMITS = {  # smallest chunk, largest chunk
    "free": (64 * _KIB, 256 * _KIB),
    "team": (64 * _KIB, 512 * _KIB),
    "business": (256 * _KIB, 2048 * _KIB),
}


def _chunk_for(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _LIMITS[key]
    if size >= hi:
        return hi
    step = 64 * _KIB
    fit = max(1, -(-size // step)) * step
    return min(hi, max(lo, fit))


def _start(transport, name, data, plan, record) -> Session:
    chunk = _chunk_for(plan, len(data))
    s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
    started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
    if record is not None:
        record(started)
    return started


def _b64(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).decode().rstrip("=")


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except ApiError as e:
        if e.status == 410 and e.code == "upload_expired":
            raise _Expired() from e
        raise


def _run(transport, data: bytes, sess: Session, resuming: bool) -> StoredFile:
    cs = sess.chunk_size
    parts = [data[o : o + cs] for o in range(0, len(data), cs)]
    digests = [hashlib.sha256(p).digest() for p in parts]
    pcs = ["sha256=" + base64.b64encode(d).decode() for d in digests]
    base = f"{BASE}/uploads/{sess.upload_id}"
    etags: dict[int, str] = {}

    def put(n: int) -> None:
        r = _guard(_call, transport, "PUT", f"{base}/parts/{n + 1}", parts[n], {"Part-Checksum": pcs[n]})
        etags[n] = r["etag"]

    if resuming:
        try:
            got = _call(transport, "GET", f"{base}/parts")
        except ApiError as e:
            if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
                raise _Expired() from e
            raise
        held = {p["part"]: p for p in got.get("parts", [])}
        for n in range(len(parts)):
            h = held.get(n + 1)
            if h and h["size"] == len(parts[n]) and h["checksum"] == pcs[n]:
                etags[n] = h["etag"]
    for n in range(len(parts)):
        if n not in etags:
            put(n)
    body = {
        "parts": [{"part": n + 1, "etag": etags[n]} for n in range(len(parts))],
        "checksum": _b64(hashlib.sha256(b"".join(digests)).digest()) + f"-{len(parts)}",
    }
    for attempt in range(2):
        try:
            return _stored(_guard(_call, transport, "POST", f"{base}/commit", body))
        except ApiError as e:
            if e.status == 409 and e.code == "parts_missing" and attempt == 0:
                missing = sorted(e.missing)
                for m in missing:
                    put(m - 1)
                body["parts"] = [{"part": n + 1, "etag": etags[n]} for n in range(len(parts))]
                continue
            raise
    raise AssertionError

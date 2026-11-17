"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
_64K = 64 * 1024
_PLANS = {
    "free": (_64K, 256 * 1024),
    "team": (_64K, 512 * 1024),
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

    def __init__(self, status: int, code: str):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code
        self.missing: list[int] = []


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
        exc.missing = missing
        raise exc
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
    key = str(plan).strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _PLANS[key]
    if len(data) >= hi:
        chunk = hi
    else:
        chunk = max(lo, -(-len(data) // _64K) * _64K)

    def cut(size: int) -> list[bytes]:
        return [data[o : o + size] for o in range(0, len(data), size)]

    def pchk(part: bytes) -> str:
        return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()

    def put(sid: str, n: int, part: bytes) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{sid}/parts/{n}", part, {"Part-Checksum": pchk(part)})
        return r["etag"]

    replaced = False
    missing_retried = False
    current: Session | None = None
    if session is not None and session.expires_at - transport.now() > 600:
        current = session
        parts = cut(session.chunk_size)
        etags: dict[int, str] = {}
        try:
            r = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
            held = {p["part"]: p for p in r["parts"]}
            for n, part in enumerate(parts, 1):
                h = held.get(n)
                if h is not None and h["size"] == len(part) and h["checksum"] == pchk(part):
                    etags[n] = h["etag"]
        except ApiError as e:
            if (e.status, e.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            current = None
            replaced = True
    resumed_etags = etags if current is not None else {}

    while True:
        if current is None:
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
            current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            if record is not None:
                record(current)
            parts = cut(current.chunk_size)
            resumed_etags = {}
        etags = dict(resumed_etags)
        sid = current.upload_id
        try:
            for n, part in enumerate(parts, 1):
                if n not in etags:
                    etags[n] = put(sid, n, part)
            digests = b"".join(hashlib.sha256(x).digest() for x in parts)
            fsum = (
                base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=") + f"-{len(parts)}"
            )
            while True:
                body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": fsum}
                try:
                    return _stored(_call(transport, "POST", f"{BASE}/uploads/{sid}/commit", body))
                except ApiError as e:
                    if (e.status, e.code) != (409, "parts_missing") or missing_retried:
                        raise
                    missing_retried = True
                    miss = e.missing
                    for n in sorted(miss):
                        etags[n] = put(sid, n, parts[n - 1])
        except ApiError as e:
            if (e.status, e.code) == (410, "upload_expired") and not replaced:
                replaced = True
                current = None
                continue
            raise

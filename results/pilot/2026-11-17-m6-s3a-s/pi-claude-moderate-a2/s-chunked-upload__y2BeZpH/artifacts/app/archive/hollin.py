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
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        err = ApiError(r.status, code)
        try:
            err.missing = [int(x) for x in json.loads(r.body)["error"]["missing"]]
        except (ValueError, KeyError, TypeError):
            pass
        raise err
    return json.loads(r.body)


_KIB = 1024
_LIMITS = {"free": (64 * _KIB, 256 * _KIB), "team": (64 * _KIB, 512 * _KIB), "business": (256 * _KIB, 2048 * _KIB)}


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _LIMITS[key]
    if size >= hi:
        return hi
    need = -(-size // (64 * _KIB)) * 64 * _KIB
    return max(lo, need)


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
    parts = [data[o : o + chunk] for o in range(0, len(data), chunk)] if data else []
    sums = [hashlib.sha256(x).digest() for x in parts]
    headers = ["sha256=" + base64.b64encode(d).decode() for d in sums]
    file_sum = (
        base64.urlsafe_b64encode(hashlib.sha256(b"".join(sums)).digest()).decode().rstrip("=") + f"-{len(parts)}"
    )

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        new = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(new)
        return new

    def put(uid: str, n: int) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{uid}/parts/{n + 1}", parts[n], {"Part-Checksum": headers[n]})
        return r["etag"]

    replaced = False
    current: Session | None = None
    if session is not None and session.expires_at > transport.now() + 600:
        current = session
    while True:
        try:
            etags: dict[int, str] = {}
            if current is None:
                current = start()
                resumed = False
            else:
                resumed = True
            chunk = current.chunk_size
            if resumed:
                # a resumed session keeps its own chunk size
                parts = [data[o : o + chunk] for o in range(0, len(data), chunk)] if data else []
                sums = [hashlib.sha256(x).digest() for x in parts]
                headers = ["sha256=" + base64.b64encode(d).decode() for d in sums]
                file_sum = (
                    base64.urlsafe_b64encode(hashlib.sha256(b"".join(sums)).digest()).decode().rstrip("=")
                    + f"-{len(parts)}"
                )
                try:
                    held = _call(transport, "GET", f"{BASE}/uploads/{current.upload_id}/parts")
                except ApiError as e:
                    if e.status == 404 and e.code == "not_found":
                        e.status = 410
                        e.code = "upload_expired"
                    raise
                for h in held["parts"]:
                    k = h["part"] - 1
                    if 0 <= k < len(parts) and h["size"] == len(parts[k]) and h["checksum"] == headers[k]:
                        etags[k] = h["etag"]
            uid = current.upload_id
            for n in range(len(parts)):
                if n not in etags:
                    etags[n] = put(uid, n)
            retried = False
            while True:
                body = {"parts": [{"part": n + 1, "etag": etags[n]} for n in range(len(parts))], "checksum": file_sum}
                try:
                    return _stored(_call(transport, "POST", f"{BASE}/uploads/{uid}/commit", body))
                except ApiError as e:
                    if e.status == 409 and e.code == "parts_missing" and not retried:
                        retried = True
                        for m in sorted(e.missing):
                            etags[m - 1] = put(uid, m - 1)
                        continue
                    raise
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired":
                if replaced:
                    raise
                replaced = True
                current = None
                chunk = _chunk_size(plan, len(data))
                parts = [data[o : o + chunk] for o in range(0, len(data), chunk)] if data else []
                sums = [hashlib.sha256(x).digest() for x in parts]
                headers = ["sha256=" + base64.b64encode(d).decode() for d in sums]
                file_sum = (
                    base64.urlsafe_b64encode(hashlib.sha256(b"".join(sums)).digest()).decode().rstrip("=")
                    + f"-{len(parts)}"
                )
                continue
            raise

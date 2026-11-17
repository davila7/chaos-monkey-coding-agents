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


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


_KIB = 1024
_LIMITS = {  # smallest chunk, largest chunk
    "free": (64 * _KIB, 256 * _KIB),
    "team": (64 * _KIB, 512 * _KIB),
    "business": (256 * _KIB, 2048 * _KIB),
}


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _LIMITS[key]
    if size >= hi:
        return hi
    fit = -(-size // (64 * _KIB)) * 64 * _KIB
    return max(lo, fit)


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


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
    parts_of = lambda cs: [data[o : o + cs] for o in range(0, len(data), cs)]
    replaced = False
    sess = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at - transport.now() > 600:
        sess = session
        try:
            got = _call(transport, "GET", f"{BASE}/uploads/{sess.upload_id}/parts")
        except ApiError as e:
            if (e.status, e.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            sess = None
            replaced = True
        else:
            local = parts_of(sess.chunk_size)
            for p in got.get("parts", []):
                n = p["part"]
                if 1 <= n <= len(local) and p["size"] == len(local[n - 1]) and p["checksum"] == _part_checksum(local[n - 1]):
                    etags[n] = p["etag"]
    while True:
        if sess is None:
            cs = _chunk_size(plan, len(data))
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": cs})
            sess = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            etags = {}
            if record is not None:
                record(sess)
        local = parts_of(sess.chunk_size)
        try:
            def send(n: int) -> None:
                part = local[n - 1]
                r = _call(transport, "PUT", f"{BASE}/uploads/{sess.upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
                etags[n] = r["etag"]

            for n in range(1, len(local) + 1):
                if n not in etags:
                    send(n)
            digest = hashlib.sha256(b"".join(hashlib.sha256(x).digest() for x in local)).digest()
            body = {
                "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(local) + 1)],
                "checksum": base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(local)}",
            }
            url = f"{BASE}/uploads/{sess.upload_id}/commit"
            try:
                return _stored(_call(transport, "POST", url, body))
            except ApiError as e:
                if (e.status, e.code) != (409, "parts_missing"):
                    raise
                missing = e.missing
            for n in sorted(missing):
                send(n)
            body["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(local) + 1)]
            return _stored(_call(transport, "POST", url, body))
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
                sess = None
                continue
            raise

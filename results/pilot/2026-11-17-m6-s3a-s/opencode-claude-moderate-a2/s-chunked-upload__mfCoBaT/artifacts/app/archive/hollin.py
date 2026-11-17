"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
_UNIT = 64 * 1024
_PLANS = {  # plan: (smallest chunk, largest chunk)
    "free": (64 * 1024, 256 * 1024),
    "team": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
}


def _limits(plan: str) -> tuple[int, int]:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    return _PLANS[key]


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


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
            missing = [int(x) for x in err.get("missing", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            code = code if "code" in locals() else ""
        e = ApiError(r.status, code)
        e.missing = missing
        raise e
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
    smallest, largest = _limits(plan)
    size = len(data)
    replaced = False

    def start() -> Session:
        chunk = min(largest, max(smallest, -(-size // _UNIT) * _UNIT))
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk})
        new = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(new)
        return new

    def parts_of(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, size, chunk)]

    def put(sess: Session, n: int, part: bytes) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{sess.upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
        return r["etag"]

    current: Session | None = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at > transport.now() + 600:
        try:
            listed = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
            current = session
            for item in listed["parts"]:
                n = item["part"]
                ps = parts_of(session.chunk_size)
                if 1 <= n <= len(ps) and item["size"] == len(ps[n - 1]) and item["checksum"] == _part_checksum(ps[n - 1]):
                    etags[n] = item["etag"]
        except ApiError as e:
            if (e.status, e.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            replaced = True
    while True:
        if current is None:
            current = start()
            etags = {}
        try:
            ps = parts_of(current.chunk_size)
            for n, part in enumerate(ps, 1):
                if n not in etags:
                    etags[n] = put(current, n, part)
            digests = b"".join(hashlib.sha256(x).digest() for x in ps)
            checksum = _b64url(hashlib.sha256(digests).digest()) + f"-{len(ps)}"
            body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(ps) + 1)], "checksum": checksum}
            try:
                return _stored(_call(transport, "POST", f"{BASE}/uploads/{current.upload_id}/commit", body))
            except ApiError as e:
                if (e.status, e.code) != (409, "parts_missing"):
                    raise
                missing = e.missing
            for n in sorted(missing):
                etags[n] = put(current, n, ps[n - 1])
            body["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(ps) + 1)]
            return _stored(_call(transport, "POST", f"{BASE}/uploads/{current.upload_id}/commit", body))
        except ApiError as e:
            if (e.status, e.code) == (410, "upload_expired") and not replaced:
                replaced = True
                current = None
                continue
            raise

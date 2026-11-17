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
        missing: list[int] = []
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            missing = [int(x) for x in err.get("missing", [])]
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
    KIB = 1024
    limits = {"free": (64 * KIB, 256 * KIB), "team": (64 * KIB, 512 * KIB), "business": (256 * KIB, 2048 * KIB)}
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = limits[key]
    if len(data) >= hi:
        chunk = hi
    else:
        unit = 64 * KIB
        chunk = max(lo, -(-len(data) // unit) * unit)

    def parts_of(size: int) -> list[bytes]:
        return [data[o : o + size] for o in range(0, len(data), size)]

    def part_sum(part: bytes) -> str:
        return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()

    def file_sum(parts: list[bytes]) -> str:
        digests = b"".join(hashlib.sha256(p).digest() for p in parts)
        enc = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=")
        return f"{enc}-{len(parts)}"

    def put(sess: Session, n: int, part: bytes) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{sess.upload_id}/parts/{n}", part, {"Part-Checksum": part_sum(part)})
        return r["etag"]

    replaced = False
    current: Session | None = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at - transport.now() > 600:
        try:
            r = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
        except ApiError as e:
            if not ((e.status == 410 and e.code == "upload_expired") or (e.status == 404 and e.code == "not_found")):
                raise
            replaced = True
        else:
            current = session
            local = parts_of(session.chunk_size)
            held = {p["part"]: p for p in r["parts"]}
            try:
                for n, part in enumerate(local, 1):
                    h = held.get(n)
                    if h is not None and h["size"] == len(part) and h["checksum"] == part_sum(part):
                        etags[n] = h["etag"]
                    else:
                        etags[n] = put(current, n, part)
            except ApiError as e:
                if e.status == 410 and e.code == "upload_expired" and not replaced:
                    replaced = True
                    current = None
                    etags = {}
                else:
                    raise
    elif session is not None:
        pass

    while True:
        if current is None:
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
            current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            etags = {}
            if record is not None:
                record(current)
            local = parts_of(current.chunk_size)
        else:
            local = parts_of(current.chunk_size)
        try:
            for n, part in enumerate(local, 1):
                if n not in etags:
                    etags[n] = put(current, n, part)
            retried = False
            while True:
                body = {
                    "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(local) + 1)],
                    "checksum": file_sum(local),
                }
                try:
                    return _stored(_call(transport, "POST", f"{BASE}/uploads/{current.upload_id}/commit", body))
                except ApiError as e:
                    if e.status == 409 and e.code == "parts_missing" and not retried:
                        retried = True
                        for n in sorted(e.missing):
                            etags[n] = put(current, n, local[n - 1])
                    else:
                        raise
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
                current = None
                etags = {}
            else:
                raise

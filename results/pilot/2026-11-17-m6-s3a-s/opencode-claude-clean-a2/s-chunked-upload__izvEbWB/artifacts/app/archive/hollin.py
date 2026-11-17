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
        err = ApiError(r.status, code)
        try:
            err.missing = [int(x) for x in json.loads(r.body)["error"]["missing"]]  # type: ignore[attr-defined]
        except (ValueError, KeyError, TypeError):
            err.missing = []  # type: ignore[attr-defined]
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
    KIB = 1024
    limits = {"free": (64 * KIB, 256 * KIB), "team": (64 * KIB, 512 * KIB), "business": (256 * KIB, 2048 * KIB)}
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = limits[key]
    if len(data) >= hi:
        want = hi
    else:
        unit = 64 * KIB
        want = max(lo, -(-len(data) // unit) * unit)

    def checksums(size: int) -> list[bytes]:
        return [hashlib.sha256(data[o : o + size]).digest() for o in range(0, len(data), size)]

    def pcs(digest: bytes) -> str:
        return "sha256=" + base64.b64encode(digest).decode()

    def send_part(sess: Session, n: int, digest: bytes) -> str:
        o = (n - 1) * sess.chunk_size
        r = _call(transport, "PUT", f"{BASE}/uploads/{sess.upload_id}/parts/{n}", data[o : o + sess.chunk_size], {"Part-Checksum": pcs(digest)})
        return r["etag"]

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": want})
        st = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(st)
        return st

    def attempt(sess: Session, resumed: bool) -> StoredFile:
        digests = checksums(sess.chunk_size)
        etags: dict[int, str] = {}
        if resumed:
            try:
                got = _call(transport, "GET", f"{BASE}/uploads/{sess.upload_id}/parts")
            except ApiError as e:
                if e.status == 404 and e.code == "not_found":
                    raise ApiError(410, "upload_expired") from e
                raise
            for item in got["parts"]:
                n = item["part"]
                if 1 <= n <= len(digests):
                    o = (n - 1) * sess.chunk_size
                    if item["size"] == len(data[o : o + sess.chunk_size]) and item["checksum"] == pcs(digests[n - 1]):
                        etags[n] = item["etag"]
        for n in range(1, len(digests) + 1):
            if n not in etags:
                etags[n] = send_part(sess, n, digests[n - 1])
        file_cs = base64.urlsafe_b64encode(hashlib.sha256(b"".join(digests)).digest()).decode().rstrip("=") + f"-{len(digests)}"
        path = f"{BASE}/uploads/{sess.upload_id}/commit"
        for tries in range(2):
            body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(digests) + 1)], "checksum": file_cs}
            try:
                return _stored(_call(transport, "POST", path, body))
            except ApiError as e:
                if e.status != 409 or e.code != "parts_missing" or tries == 1:
                    raise
                missing = e.missing
            for n in sorted(missing):
                etags[n] = send_part(sess, n, digests[n - 1])
        raise AssertionError

    if session is not None and session.expires_at > transport.now() + 600:
        current, resumed = session, True
    else:
        current, resumed = start(), False
    replaced = False
    while True:
        try:
            return attempt(current, resumed)
        except ApiError as e:
            gone = e.status == 410 and e.code == "upload_expired"
            if not gone or replaced:
                raise
            replaced = True
            current, resumed = start(), False

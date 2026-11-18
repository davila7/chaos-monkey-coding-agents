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


class _Gone(Exception):
    """The saved session cannot be read any more."""


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        err = ApiError(r.status, code)
        try:
            err.missing = [int(n) for n in json.loads(r.body)["error"]["missing"]]
        except (ValueError, KeyError, TypeError):
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
    KIB = 1024
    limits = {"free": (64 * KIB, 256 * KIB), "team": (64 * KIB, 512 * KIB), "business": (256 * KIB, 2048 * KIB)}
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    smallest, largest = limits[key]

    def new_chunk() -> int:
        if len(data) >= largest:
            return largest
        need = -(-len(data) // (64 * KIB)) * 64 * KIB
        return max(need, smallest)

    def cut(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    def part_sum(part: bytes) -> str:
        return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()

    def file_sum(parts: list[bytes]) -> str:
        digests = b"".join(hashlib.sha256(x).digest() for x in parts)
        enc = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=")
        return f"{enc}-{len(parts)}"

    def send_part(upload_id: str, n: int, part: bytes) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{n}", part, {"Part-Checksum": part_sum(part)})
        return r["etag"]

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": new_chunk()})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    def run(sess: Session, resumed: bool) -> StoredFile:
        parts = cut(sess.chunk_size)
        etags: dict[int, str] = {}
        if resumed:
            try:
                got = _call(transport, "GET", f"{BASE}/uploads/{sess.upload_id}/parts")
            except ApiError as e:
                if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
                    raise _Gone() from e
                raise
            for rp in got["parts"]:
                n = rp["part"]
                if 1 <= n <= len(parts):
                    local = parts[n - 1]
                    if rp["size"] == len(local) and rp["checksum"] == part_sum(local):
                        etags[n] = rp["etag"]
        for n, part in enumerate(parts, 1):
            if n not in etags:
                etags[n] = send_part(sess.upload_id, n, part)
        checksum = file_sum(parts)
        retried = False
        while True:
            body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
            try:
                return _stored(_call(transport, "POST", f"{BASE}/uploads/{sess.upload_id}/commit", body))
            except ApiError as e:
                if e.status == 409 and e.code == "parts_missing" and not retried:
                    retried = True
                    missing = e.missing
                    for n in sorted(missing):
                        etags[n] = send_part(sess.upload_id, n, parts[n - 1])
                else:
                    raise

    usable = session is not None and session.expires_at > transport.now() + 600
    replaced = False
    current = session if usable else start()
    resumed = usable
    while True:
        try:
            return run(current, resumed)
        except ApiError as e:
            if e.status != 410 or e.code != "upload_expired" or replaced:
                raise
            replaced = True
            current = start()
            resumed = False
        except _Gone:
            if replaced:
                raise ApiError(410, "upload_expired")
            replaced = True
            current = start()
            resumed = False

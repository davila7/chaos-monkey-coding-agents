"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
# plan -> (smallest chunk, largest chunk)
PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}
STEP = 64 * KIB
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
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            missing = err.get("missing") or []
        except (ValueError, KeyError, TypeError, AttributeError):
            code = ""
            missing = []
        e = ApiError(r.status, code)
        e.missing = list(missing)
        raise e
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLANS[plan.strip().lower()]
    fit = -(-size // STEP) * STEP
    return min(largest, max(smallest, fit))


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    enc = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=")
    return f"{enc}-{len(parts)}"


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

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    def cut(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    def put(sess: Session, n: int, part: bytes) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{sess.upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
        return r["etag"]

    current: Session | None = None
    etags: dict[int, str] = {}
    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        try:
            listed = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
        except ApiError as e:
            if (e.status, e.code) not in ((410, "upload_expired"), (404, "not_found")):
                raise
            replaced = True
        else:
            current = session
            parts = cut(session.chunk_size)
            held = {p["part"]: p for p in listed["parts"]}
            for n, part in enumerate(parts, 1):
                h = held.get(n)
                if h is not None and h["size"] == len(part) and h["checksum"] == _part_checksum(part):
                    etags[n] = h["etag"]
    resumed = current is not None

    while True:
        try:
            if current is None:
                current = start()
                etags = {}
            parts = cut(current.chunk_size)
            for n, part in enumerate(parts, 1):
                if n not in etags:
                    etags[n] = put(current, n, part)
            checksum = _file_checksum(parts)
            retried = False
            while True:
                commit = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
                try:
                    return _stored(_call(transport, "POST", f"{BASE}/uploads/{current.upload_id}/commit", commit))
                except ApiError as e:
                    if e.status != 409 or e.code != "parts_missing" or retried:
                        raise
                    retried = True
                    for n in sorted(e.missing):
                        etags[n] = put(current, n, parts[n - 1])
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
                current = None
                continue
            raise

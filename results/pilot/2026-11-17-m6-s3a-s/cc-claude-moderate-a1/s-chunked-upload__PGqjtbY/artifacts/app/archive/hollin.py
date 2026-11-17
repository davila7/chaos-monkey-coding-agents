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
        missing: list[int] = []
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            missing = list(err.get("missing") or [])
        except (ValueError, KeyError, TypeError, AttributeError):
            code = ""
        exc = ApiError(r.status, code)
        exc.missing = missing  # type: ignore[attr-defined]
        raise exc
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


KIB = 1024
PLANS = {  # smallest chunk, largest chunk
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}
RESUME_MARGIN = 600


class _Expired(Exception):
    pass


def _chunk_size(plan: str, size: int) -> int:
    low, high = PLANS[plan.strip().lower()]
    if size >= high:
        return high
    need = -(-size // (64 * KIB)) * 64 * KIB
    return max(low, need)


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    return f"{hashlib.sha256(digests).hexdigest()}-{len(parts)}"


def _is(e: ApiError, status: int, code: str) -> bool:
    return e.status == status and e.code == code


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
        chunk = _chunk_size(plan, len(data))
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    def attempt(sess: Session, resume: bool) -> StoredFile:
        base = f"{BASE}/uploads/{sess.upload_id}"
        parts = [data[o : o + sess.chunk_size] for o in range(0, len(data), sess.chunk_size)]
        etags: dict[int, str] = {}

        def send(n: int) -> None:
            part = parts[n - 1]
            r = _call(transport, "PUT", f"{base}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
            etags[n] = r["etag"]

        try:
            if resume:
                try:
                    got = _call(transport, "GET", f"{base}/parts")
                except ApiError as e:
                    if _is(e, 404, "not_found"):
                        raise _Expired() from e
                    raise
                held = {p["part"]: p for p in got["parts"]}
                for n, part in enumerate(parts, 1):
                    h = held.get(n)
                    if h is not None and h["size"] == len(part) and h["checksum"] == _part_checksum(part):
                        etags[n] = h["etag"]
                    else:
                        send(n)
            else:
                for n in range(1, len(parts) + 1):
                    send(n)
            checksum = _file_checksum(parts)
            retried = False
            while True:
                body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
                try:
                    return _stored(_call(transport, "POST", f"{base}/commit", body))
                except ApiError as e:
                    if not _is(e, 409, "parts_missing") or retried:
                        raise
                    retried = True
                    for n in sorted(e.missing):  # type: ignore[attr-defined]
                        send(n)
        except ApiError as e:
            if _is(e, 410, "upload_expired"):
                raise _Expired() from e
            raise

    current = session
    resume = session is not None and session.expires_at > transport.now() + RESUME_MARGIN
    if not resume:
        current = start()
    while True:
        try:
            return attempt(current, resume)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired") from None
            replaced = True
            current = start()
            resume = False



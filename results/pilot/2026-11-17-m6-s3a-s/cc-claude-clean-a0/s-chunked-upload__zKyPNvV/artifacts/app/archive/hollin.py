"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
MIB = 1024 * KIB
GIB = 1024 * MIB
UNIT = 64 * KIB
RESUME_MARGIN = 600
# plan -> (smallest chunk, largest chunk)
PLAN_CHUNKS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2 * MIB),
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


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        missing: list[int] = []
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            missing = [int(n) for n in err.get("missing", [])]
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


def _chunk_size(plan: str, size: int) -> int:
    lo, hi = PLAN_CHUNKS[plan.strip().lower()]
    if size >= hi:
        return hi
    return max(lo, -(-size // UNIT) * UNIT)


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode()


def _file_checksum(digests: list[bytes]) -> str:
    h = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(h).decode().rstrip("=") + f"-{len(digests)}"


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
    chunk = _chunk_size(plan, len(data))
    replaced = False  # whether the one replacement session has been used

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    current: Session | None = None
    held: dict[int, dict[str, Any]] | None = None  # received parts of a resumed session
    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        try:
            r = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
            current = session
            held = {p["part"]: p for p in r["parts"]}
        except ApiError as e:
            if not (_is(e, 410, "upload_expired") or _is(e, 404, "not_found")):
                raise
            replaced = True
    while True:
        if current is None:
            current = start()
            held = None
        size = current.chunk_size
        parts = [data[o : o + size] for o in range(0, len(data), size)]
        digests = [hashlib.sha256(p).digest() for p in parts]
        etags: dict[int, str] = {}
        base = f"{BASE}/uploads/{current.upload_id}"

        def send(n: int) -> None:
            r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": _part_checksum(digests[n - 1])})
            etags[n] = r["etag"]

        try:
            for n in range(1, len(parts) + 1):
                h = held.get(n) if held else None
                if h is not None and h["size"] == len(parts[n - 1]) and h["checksum"] == _part_checksum(digests[n - 1]):
                    etags[n] = h["etag"]
                else:
                    send(n)
            commit = {
                "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
                "checksum": _file_checksum(digests),
            }
            try:
                return _stored(_call(transport, "POST", f"{base}/commit", commit))
            except ApiError as e:
                if not _is(e, 409, "parts_missing"):
                    raise
                missing = getattr(e, "missing", [])
            for n in sorted(missing):
                send(n)
            commit["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
            return _stored(_call(transport, "POST", f"{base}/commit", commit))
        except ApiError as e:
            if not _is(e, 410, "upload_expired") or replaced:
                raise
            replaced = True
            current = None

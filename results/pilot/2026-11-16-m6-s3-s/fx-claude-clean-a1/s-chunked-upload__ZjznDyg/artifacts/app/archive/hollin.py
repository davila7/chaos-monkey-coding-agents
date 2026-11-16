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
UNIT = 64 * KIB  # chunk sizes are multiples of this

# plan -> (smallest chunk, largest chunk, largest file)
PLANS = {
    "free": (64 * KIB, 256 * KIB, 4 * MIB),
    "team": (64 * KIB, 512 * KIB, 64 * MIB),
    "business": (256 * KIB, 2 * MIB, 1 * GIB),
}
PLAN_ALIASES = {"pro": "team"}  # renamed on 2026-07-01

RESUME_MARGIN = 600  # seconds a saved session must still live to be resumed


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
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            if isinstance(error, dict) and isinstance(error.get("missing"), list):
                missing = [int(n) for n in error["missing"]]
        except (ValueError, KeyError, TypeError):
            code = ""
        err = ApiError(r.status, code)
        err.missing = missing  # type: ignore[attr-defined]
        raise err
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _chunk_size(plan: str, size: int) -> int:
    key = str(plan).strip().lower()
    key = PLAN_ALIASES.get(key, key)
    smallest, largest, _ = PLANS[key]
    if size >= largest:
        return largest
    fitting = -(-size // UNIT) * UNIT  # smallest multiple of 64 KiB holding the whole file
    return min(largest, max(smallest, fitting))


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode("ascii")


def _file_checksum(digests: list[bytes]) -> str:
    total = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(total).decode("ascii").rstrip("=") + f"-{len(digests)}"


def _is_expired(e: ApiError) -> bool:
    return e.status == 410 and e.code == "upload_expired"


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
    replaced = False  # whether the one replacement session has been used
    received: dict[int, dict[str, Any]] | None = None  # parts held by a resumed session

    if session is not None:
        if session.expires_at - transport.now() > RESUME_MARGIN:
            try:
                listing = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
                received = {int(p["part"]): p for p in listing["parts"]}
            except ApiError as e:
                if _is_expired(e) or (e.status == 404 and e.code == "not_found"):
                    replaced = True
                    session = None
                else:
                    raise
        else:
            session = None

    while True:
        if session is None:
            chunk = _chunk_size(plan, len(data))
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
            session = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            received = None
            if record is not None:
                record(session)
        try:
            return _run(transport, session, data, received)
        except ApiError as e:
            if not _is_expired(e) or replaced:
                raise
            replaced = True
            session = None


def _run(transport: Transport, session: Session, data: bytes, received: dict[int, dict[str, Any]] | None) -> StoredFile:
    """Sends the missing parts of `data` to `session` and commits it."""
    size = session.chunk_size
    parts = [data[offset : offset + size] for offset in range(0, len(data), size)]
    digests = [hashlib.sha256(p).digest() for p in parts]
    base = f"{BASE}/uploads/{session.upload_id}"
    etags: dict[int, str] = {}

    def send(n: int) -> None:
        r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": _part_checksum(digests[n - 1])})
        etags[n] = r["etag"]

    for n in range(1, len(parts) + 1):
        have = received.get(n) if received is not None else None
        if have is not None and have.get("size") == len(parts[n - 1]) and have.get("checksum") == _part_checksum(digests[n - 1]):
            etags[n] = have["etag"]
        else:
            send(n)

    checksum = _file_checksum(digests)
    retried = False
    while True:
        body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
        try:
            return _stored(_call(transport, "POST", f"{base}/commit", body))
        except ApiError as e:
            if e.status == 409 and e.code == "parts_missing" and not retried:
                retried = True
                for n in sorted(set(getattr(e, "missing", []))):
                    if 1 <= n <= len(parts):
                        send(n)
                continue
            raise

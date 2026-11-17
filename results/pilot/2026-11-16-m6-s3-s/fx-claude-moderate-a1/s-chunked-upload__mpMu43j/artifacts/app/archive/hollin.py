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
STEP = 64 * KIB  # chunk sizes are multiples of this

# plan -> (smallest chunk, largest chunk)
_PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2 * MIB),
}
_PLAN_ALIASES = {"pro": "team"}  # renamed on 2026-07-01

RESUME_MARGIN = 600  # seconds a saved session must still have left to be resumed


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


def _error_object(r: Response) -> dict[str, Any]:
    try:
        err = json.loads(r.body)["error"]
    except (ValueError, KeyError, TypeError):
        return {}
    return err if isinstance(err, dict) else {}


def _api_error(r: Response) -> ApiError:
    return ApiError(r.status, str(_error_object(r).get("code", "")))


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        raise _api_error(r)
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _limits(plan: str) -> tuple[int, int]:
    key = plan.strip().lower()
    key = _PLAN_ALIASES.get(key, key)
    try:
        return _PLANS[key]
    except KeyError:
        raise ValueError(f"unknown plan: {plan!r}") from None


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = _limits(plan)
    if size >= largest:
        return largest
    fitted = -(-size // STEP) * STEP
    return min(largest, max(smallest, fitted))


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode("ascii")


def _file_checksum(digests: list[bytes]) -> str:
    joined = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(joined).rstrip(b"=").decode("ascii") + f"-{len(digests)}"


class _Expired(Exception):
    """The session expired or was dropped (410 upload_expired)."""


class _Parts:
    """The local parts of a file for one chunk size."""

    def __init__(self, data: bytes, chunk_size: int):
        self.data = [data[o : o + chunk_size] for o in range(0, len(data), chunk_size)]
        self.digests = [hashlib.sha256(p).digest() for p in self.data]
        self.checksum = _file_checksum(self.digests)

    def __len__(self) -> int:
        return len(self.data)


def _send_part(transport: Transport, session: Session, parts: _Parts, number: int) -> str:
    path = f"{BASE}/uploads/{session.upload_id}/parts/{number}"
    headers = {"Part-Checksum": _part_checksum(parts.digests[number - 1])}
    r = transport.send("PUT", path, headers, parts.data[number - 1])
    if r.status != 200:
        err = _api_error(r)
        if err.status == 410 and err.code == "upload_expired":
            raise _Expired()
        raise err
    return json.loads(r.body)["etag"]


def _commit(transport: Transport, session: Session, parts: _Parts, etags: dict[int, str]) -> StoredFile:
    """Commits once; returns the file, or raises _Expired / ApiError. parts_missing is raised as _Missing."""
    body = {
        "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
        "checksum": parts.checksum,
    }
    r = transport.send("POST", f"{BASE}/uploads/{session.upload_id}/commit", {}, body)
    if r.status in (200, 201):
        return _stored(json.loads(r.body))
    err = _api_error(r)
    if err.status == 410 and err.code == "upload_expired":
        raise _Expired()
    if err.status == 409 and err.code == "parts_missing":
        missing = _error_object(r).get("missing") or []
        raise _Missing(sorted(int(n) for n in missing))
    raise err


class _Missing(Exception):
    def __init__(self, missing: list[int]):
        super().__init__("parts_missing")
        self.missing = missing


def _finish(transport: Transport, session: Session, parts: _Parts, etags: dict[int, str], to_send: list[int]) -> StoredFile:
    """Sends `to_send` (ascending), then commits; after parts_missing sends those parts and commits once more."""
    for n in to_send:
        etags[n] = _send_part(transport, session, parts, n)
    try:
        return _commit(transport, session, parts, etags)
    except _Missing as m:
        for n in m.missing:
            etags[n] = _send_part(transport, session, parts, n)
    try:
        return _commit(transport, session, parts, etags)
    except _Missing as m:
        raise ApiError(409, "parts_missing") from None


def _resume(transport: Transport, session: Session, data: bytes) -> StoredFile:
    """Resumes a saved session. Raises _Expired when the session is gone."""
    r = transport.send("GET", f"{BASE}/uploads/{session.upload_id}/parts", {}, None)
    if r.status != 200:
        err = _api_error(r)
        if (err.status, err.code) in ((410, "upload_expired"), (404, "not_found")):
            raise _Expired()
        raise err
    received = {}
    for p in json.loads(r.body).get("parts", []):
        received[p["part"]] = p
    parts = _Parts(data, session.chunk_size)
    etags: dict[int, str] = {}
    to_send = []
    for n in range(1, len(parts) + 1):
        p = received.get(n)
        if p is not None and p["size"] == len(parts.data[n - 1]) and p["checksum"] == _part_checksum(parts.digests[n - 1]):
            etags[n] = p["etag"]
        else:
            to_send.append(n)
    return _finish(transport, session, parts, etags, to_send)


def _fresh(transport: Transport, name: str, data: bytes, plan: str, record: Callable[[Session], None] | None) -> StoredFile:
    chunk = _chunk_size(plan, len(data))
    s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
    started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
    if record is not None:
        record(started)
    parts = _Parts(data, started.chunk_size)
    return _finish(transport, started, parts, {}, list(range(1, len(parts) + 1)))


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
    _limits(plan)  # reject an unknown plan before sending anything
    replaced = False
    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        try:
            return _resume(transport, session, data)
        except _Expired:
            replaced = True  # the session started next is the replacement
    if not replaced:
        try:
            return _fresh(transport, name, data, plan, record)
        except _Expired:
            pass
    # the one replacement session this call may start
    try:
        return _fresh(transport, name, data, plan, record)
    except _Expired:
        raise ApiError(410, "upload_expired") from None

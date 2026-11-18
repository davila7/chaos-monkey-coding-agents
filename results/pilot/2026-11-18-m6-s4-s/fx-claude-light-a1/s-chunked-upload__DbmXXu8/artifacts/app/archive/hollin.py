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
CHUNK_UNIT = 64 * KIB
RESUME_MARGIN = 600  # seconds a saved session must still have left to be resumed

# plan -> (smallest chunk, largest chunk); "pro" is the old name of "team"
_PLANS = {
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
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            found = error.get("missing")
            if isinstance(found, list):
                missing = [m for m in found if isinstance(m, int)]
        except (ValueError, KeyError, TypeError, AttributeError):
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


def _is_expired(e: ApiError) -> bool:
    return e.status == 410 and e.code == "upload_expired"


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode("ascii")


def _file_checksum(digests: list[bytes]) -> str:
    h = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(h).decode("ascii").rstrip("=") + f"-{len(digests)}"


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower() if isinstance(plan, str) else plan
    if key not in _PLANS:
        raise ValueError(f"unknown plan: {plan!r}")
    smallest, largest = _PLANS[key]
    if size >= largest:
        return largest
    needed = -(-size // CHUNK_UNIT) * CHUNK_UNIT
    return min(largest, max(smallest, needed))


class _Expired(Exception):
    pass


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
    replaced = False  # whether the one replacement session was already used
    current: Session | None = None
    etags: dict[int, str] = {}
    to_send: list[int] = []

    def split(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        parts = split(session.chunk_size)
        try:
            listing = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
        except ApiError as e:
            if _is_expired(e) or (e.status == 404 and e.code == "not_found"):
                replaced = True
            else:
                raise
        else:
            held = {p["part"]: p for p in listing.get("parts", [])}
            current = session
            for n, part in enumerate(parts, 1):
                p = held.get(n)
                if p is not None and p.get("size") == len(part) and p.get("checksum") == _part_checksum(hashlib.sha256(part).digest()):
                    etags[n] = p["etag"]
                else:
                    to_send.append(n)

    while True:
        if current is None:
            chunk = _chunk_size(plan, len(data))
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
            current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            if record is not None:
                record(current)
            etags = {}
            to_send = list(range(1, len(split(current.chunk_size)) + 1))
        parts = split(current.chunk_size)
        digests = [hashlib.sha256(p).digest() for p in parts]
        base = f"{BASE}/uploads/{current.upload_id}"
        try:
            retried_commit = False
            while True:
                for n in to_send:
                    r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": _part_checksum(digests[n - 1])})
                    etags[n] = r["etag"]
                body = {
                    "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
                    "checksum": _file_checksum(digests),
                }
                try:
                    return _stored(_call(transport, "POST", f"{base}/commit", body))
                except ApiError as e:
                    if e.status == 409 and e.code == "parts_missing" and not retried_commit:
                        retried_commit = True
                        to_send = sorted({m for m in getattr(e, "missing", []) if 1 <= m <= len(parts)})
                        continue
                    raise
        except ApiError as e:
            if _is_expired(e) and not replaced:
                replaced = True
                current = None
                continue
            raise

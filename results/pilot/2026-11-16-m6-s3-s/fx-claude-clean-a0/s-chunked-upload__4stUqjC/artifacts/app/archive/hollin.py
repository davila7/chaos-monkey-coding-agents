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

# plan -> (smallest chunk, largest chunk, largest file)
PLANS = {
    "free": (64 * KIB, 256 * KIB, 4 * MIB),
    "team": (64 * KIB, 512 * KIB, 64 * MIB),
    "business": (256 * KIB, 2 * MIB, 1 * GIB),
}
PLAN_ALIASES = {"pro": "team"}


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
            details = json.loads(r.body)["error"]
        except (ValueError, KeyError, TypeError):
            code = ""
            details = {}
        error = ApiError(r.status, code)
        error.details = details if isinstance(details, dict) else {}
        raise error
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
    data = bytes(data)
    replaced = False  # whether this call has used its one replacement session

    def fresh() -> tuple[Session, dict[int, str]]:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started, {}

    def resumed(saved: Session) -> tuple[Session, dict[int, str]]:
        r = _call(transport, "GET", f"{BASE}/uploads/{saved.upload_id}/parts")
        local = _parts(data, saved.chunk_size)
        held: dict[int, str] = {}
        for p in r.get("parts", []):
            n = p.get("part")
            if isinstance(n, int) and 1 <= n <= len(local):
                if p.get("size") == len(local[n - 1]) and p.get("checksum") == _part_checksum(local[n - 1]):
                    held[n] = p["etag"]
        return saved, held

    current: Session | None = None
    held: dict[int, str] = {}
    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        try:
            current, held = resumed(session)
        except ApiError as e:
            if not ((e.status == 410 and e.code == "upload_expired") or (e.status == 404 and e.code == "not_found")):
                raise
            replaced = True
    while True:
        if current is None:
            current, held = fresh()
        try:
            return _finish(transport, current, data, held)
        except ApiError as e:
            if e.status != 410 or e.code != "upload_expired" or replaced:
                raise
            replaced = True
            current = None


def _chunk_size(plan: str, size: int) -> int:
    key = str(plan).strip().lower()
    key = PLAN_ALIASES.get(key, key)
    smallest, largest, _ = PLANS[key]
    if size >= largest:
        return largest
    fit = -(-size // UNIT) * UNIT
    return max(smallest, fit)


def _parts(data: bytes, chunk: int) -> list[bytes]:
    return [data[o : o + chunk] for o in range(0, len(data), chunk)]


def _part_digest(part: bytes) -> bytes:
    return hashlib.sha256(part).digest()


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(_part_digest(part)).decode("ascii")


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(_part_digest(p) for p in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=") + f"-{len(parts)}"


def _finish(transport: Transport, session: Session, data: bytes, held: dict[int, str]) -> StoredFile:
    parts = _parts(data, session.chunk_size)
    etags = dict(held)
    base = f"{BASE}/uploads/{session.upload_id}"

    def send(n: int) -> None:
        part = parts[n - 1]
        r = _call(transport, "PUT", f"{base}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
        etags[n] = r["etag"]

    for n in range(1, len(parts) + 1):
        if n not in etags:
            send(n)
    commit = {"checksum": _file_checksum(parts)}

    def do_commit() -> StoredFile:
        listed = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
        return _stored(_call(transport, "POST", f"{base}/commit", {"parts": listed, "checksum": commit["checksum"]}))

    try:
        return do_commit()
    except ApiError as e:
        if not (e.status == 409 and e.code == "parts_missing"):
            raise
        missing = getattr(e, "details", {}).get("missing", [])
    for n in sorted({m for m in missing if isinstance(m, int) and 1 <= m <= len(parts)}):
        send(n)
    return do_commit()

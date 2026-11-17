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
# plan -> (smallest chunk, largest chunk, largest file)
PLANS = {
    "free": (64 * KIB, 256 * KIB, 4 * MIB),
    "team": (64 * KIB, 512 * KIB, 64 * MIB),
    "business": (256 * KIB, 2 * MIB, GIB),
}
MIN_RESUME_SECONDS = 600


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
        code, missing = "", []
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
            missing = list(error.get("missing") or [])
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
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
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    smallest, largest, _ = PLANS[key]
    if size >= largest:
        return largest
    unit = 64 * KIB
    fitted = max(-(-size // unit), 1) * unit
    return min(max(fitted, smallest), largest)


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


def _send_part(transport: Transport, upload_id: str, n: int, part: bytes) -> str:
    r = _call(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
    return r["etag"]


def _missing(transport: Transport, e: ApiError) -> list[int]:
    return list(getattr(e, "missing", []))


def _error_code(e: ApiError, status: int, code: str) -> bool:
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
    current = session
    if current is not None and not current.expires_at - transport.now() > MIN_RESUME_SECONDS:
        current = None
    while True:
        etags: dict[int, str] = {}
        if current is None:
            s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
            current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
            if record is not None:
                record(current)
            resuming = False
        else:
            resuming = True
        size = current.chunk_size
        parts = [data[o : o + size] for o in range(0, len(data), size)]
        uid = current.upload_id
        try:
            if resuming:
                try:
                    held = _call(transport, "GET", f"{BASE}/uploads/{uid}/parts")["parts"]
                except ApiError as e:
                    if replaced or not (_error_code(e, 410, "upload_expired") or _error_code(e, 404, "not_found")):
                        raise
                    replaced = True
                    current = None
                    continue
                for h in held:
                    n = h["part"]
                    if 1 <= n <= len(parts) and h["size"] == len(parts[n - 1]) and h["checksum"] == _part_checksum(parts[n - 1]):
                        etags[n] = h["etag"]
            for n, part in enumerate(parts, 1):
                if n not in etags:
                    etags[n] = _send_part(transport, uid, n, part)
            commit = {
                "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
                "checksum": _file_checksum(parts),
            }
            try:
                return _stored(_call(transport, "POST", f"{BASE}/uploads/{uid}/commit", commit))
            except ApiError as e:
                if not _error_code(e, 409, "parts_missing"):
                    raise
                missing = _missing(transport, e)
            for n in sorted(missing):
                etags[n] = _send_part(transport, uid, n, parts[n - 1])
            commit["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
            return _stored(_call(transport, "POST", f"{BASE}/uploads/{uid}/commit", commit))
        except ApiError as e:
            if replaced or not _error_code(e, 410, "upload_expired"):
                raise
            replaced = True
            current = None

"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"


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
        raise ApiError(r.status, code)
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


_KIB = 1024
_PLANS = {  # plan -> (smallest chunk, largest chunk)
    "free": (64 * _KIB, 256 * _KIB),
    "team": (64 * _KIB, 512 * _KIB),
    "business": (256 * _KIB, 2048 * _KIB),
}
_PLAN_ALIASES = {"pro": "team"}  # renamed 2026-07-01
_MIN_RESUME_SECONDS = 600


class _Expired(Exception):
    """410 upload_expired from a call on a session."""


class _PartsMissing(Exception):
    def __init__(self, missing: list[int]):
        super().__init__("parts_missing")
        self.missing = missing


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    key = _PLAN_ALIASES.get(key, key)
    if key not in _PLANS:
        raise ValueError(f"unknown plan: {plan!r}")
    smallest, largest = _PLANS[key]
    if size >= largest:
        return largest
    unit = 64 * _KIB
    fitting = -(-size // unit) * unit
    return max(smallest, fitting)


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode("ascii")


def _file_checksum(digests: list[bytes]) -> str:
    whole = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(whole).decode("ascii").rstrip("=") + f"-{len(digests)}"


def _error(r: Response) -> tuple[ApiError, Any]:
    try:
        err = json.loads(r.body)["error"]
        code = str(err["code"])
    except (ValueError, KeyError, TypeError):
        err, code = {}, ""
    return ApiError(r.status, code), err


def _request(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    """Like _call, but a 410 upload_expired raises _Expired."""
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        exc, err = _error(r)
        if r.status == 410 and exc.code == "upload_expired":
            raise _Expired()
        if r.status == 409 and exc.code == "parts_missing" and path.endswith("/commit"):
            missing = err.get("missing") if isinstance(err, dict) else None
            if isinstance(missing, list) and all(isinstance(m, int) for m in missing):
                raise _PartsMissing(sorted(missing))
        raise exc
    return json.loads(r.body)


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
    size = len(data)
    chunk_size = _chunk_size(plan, size)  # validates the plan before anything is sent
    replacement_used = False
    current = session
    if current is not None and not current.expires_at > transport.now() + _MIN_RESUME_SECONDS:
        current = None

    while True:
        try:
            if current is None:
                s = _request(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk_size})
                current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
                if record is not None:
                    record(current)
                resuming = False
            else:
                resuming = True
            step = current.chunk_size
            chunks = [data[o : o + step] for o in range(0, size, step)]
            digests = [hashlib.sha256(c).digest() for c in chunks]
            base = f"{BASE}/uploads/{current.upload_id}"
            etags: dict[int, str] = {}
            if resuming:
                try:
                    listing = _request(transport, "GET", f"{base}/parts")
                except _Expired:
                    raise
                except ApiError as e:
                    if e.status == 404 and e.code == "not_found":
                        raise _Expired() from None
                    raise
                for p in listing.get("parts", []):
                    n = p.get("part")
                    if isinstance(n, int) and 1 <= n <= len(chunks):
                        if p.get("size") == len(chunks[n - 1]) and p.get("checksum") == _part_checksum(digests[n - 1]):
                            etags[n] = p["etag"]

            def send(n: int) -> None:
                r = _request(
                    transport,
                    "PUT",
                    f"{base}/parts/{n}",
                    chunks[n - 1],
                    {"Part-Checksum": _part_checksum(digests[n - 1])},
                )
                etags[n] = r["etag"]

            for n in range(1, len(chunks) + 1):
                if n not in etags:
                    send(n)
            file_checksum = _file_checksum(digests)
            retried_missing = False
            while True:
                commit = {
                    "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(chunks) + 1)],
                    "checksum": file_checksum,
                }
                try:
                    return _stored(_request(transport, "POST", f"{base}/commit", commit))
                except _PartsMissing as pm:
                    if retried_missing:
                        raise ApiError(409, "parts_missing") from None
                    retried_missing = True
                    for n in pm.missing:
                        if 1 <= n <= len(chunks):
                            send(n)
        except _Expired:
            if replacement_used:
                raise ApiError(410, "upload_expired") from None
            replacement_used = True
            current = None

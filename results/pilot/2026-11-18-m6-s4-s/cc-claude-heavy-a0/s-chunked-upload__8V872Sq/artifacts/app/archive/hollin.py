"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
UNIT = 64 * 1024
RESUME_MARGIN = 600
PLANS = {"free": (UNIT, 256 * 1024), "team": (UNIT, 512 * 1024), "business": (256 * 1024, 2 * 1024 * 1024)}
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
    replaced = False
    resume = session is not None and session.expires_at - transport.now() > RESUME_MARGIN
    current = session if resume else None
    while True:
        try:
            if current is None:
                s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
                current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
                if record is not None:
                    record(current)
                etags: dict[int, str] = {}
            else:
                etags = _received(transport, current, data)
            return _send_and_commit(transport, current, data, etags)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired") from None
            replaced = True
            current = None


class _Expired(ApiError):
    pass


def _api(transport: Transport, *args: Any, **kwargs: Any) -> Any:
    try:
        return _call(transport, *args, **kwargs)
    except ApiError as e:
        if e.status == 410 and e.code == "upload_expired":
            raise _Expired(e.status, e.code) from None
        raise e


def _chunk_size(plan: str, size: int) -> int:
    lo, hi = PLANS[PLAN_ALIASES.get(plan.strip().lower(), plan.strip().lower())]
    if size >= hi:
        return hi
    return max(lo, -(-size // UNIT) * UNIT)


def _parts(data: bytes, chunk: int) -> list[bytes]:
    return [data[o : o + chunk] for o in range(0, len(data), chunk)]


def _checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _received(transport: Transport, session: Session, data: bytes) -> dict[int, str]:
    """Etags of the parts Hollin already holds correctly. A dead session raises _Expired."""
    try:
        got = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
    except ApiError as e:
        if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
            raise _Expired(e.status, e.code) from None
        raise
    local = _parts(data, session.chunk_size)
    etags: dict[int, str] = {}
    for p in got["parts"]:
        n = p["part"]
        if 1 <= n <= len(local) and p["size"] == len(local[n - 1]) and p["checksum"] == _checksum(local[n - 1]):
            etags[n] = p["etag"]
    return etags


def _send(transport: Transport, session: Session, part: bytes, n: int) -> str:
    r = _api(transport, "PUT", f"{BASE}/uploads/{session.upload_id}/parts/{n}", part, {"Part-Checksum": _checksum(part)})
    return r["etag"]


def _send_and_commit(transport: Transport, session: Session, data: bytes, etags: dict[int, str]) -> StoredFile:
    parts = _parts(data, session.chunk_size)
    for n, part in enumerate(parts, 1):
        if n not in etags:
            etags[n] = _send(transport, session, part, n)
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    file_checksum = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=") + f"-{len(parts)}"
    commit = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": file_checksum}
    path = f"{BASE}/uploads/{session.upload_id}/commit"
    try:
        return _stored(_api(transport, "POST", path, commit))
    except ApiError as e:
        if isinstance(e, _Expired) or (e.status, e.code) != (409, "parts_missing"):
            raise
        missing = getattr(e, "missing", [])
    for n in sorted(missing):
        etags[n] = _send(transport, session, parts[n - 1], n)
    commit["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
    return _stored(_api(transport, "POST", path, commit))

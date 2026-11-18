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
# plan -> (smallest chunk, largest chunk)
PLANS = {
    "free": (64 * 1024, 256 * 1024),
    "team": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
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
    smallest, largest = _limits(plan)
    resume = session is not None and session.expires_at - transport.now() > RESUME_MARGIN
    replaced = False
    current = session if resume else None
    while True:
        resumed = current is not None
        try:
            if current is None:
                chunk = _chunk_size(len(data), smallest, largest)
                s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
                current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
                if record is not None:
                    record(current)
            return _upload_to(transport, current, data, resumed)
        except _Expired:
            if replaced:
                raise ApiError(410, "upload_expired") from None
            replaced = True
            current = None


class _Expired(Exception):
    pass


def _limits(plan: str) -> tuple[int, int]:
    key = plan.strip().lower()
    key = "team" if key == "pro" else key
    try:
        return PLANS[key]
    except KeyError:
        raise ValueError(f"unknown plan: {plan!r}") from None


def _chunk_size(size: int, smallest: int, largest: int) -> int:
    if size >= largest:
        return largest
    fit = -(-size // UNIT) * UNIT
    return max(smallest, fit)


def _checked(transport: Transport, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None) -> Any:
    """Like _call, but an expired session raises _Expired."""
    try:
        return _call(transport, method, path, body, headers)
    except ApiError as e:
        if e.status == 410 and e.code == "upload_expired":
            raise _Expired from None
        raise


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _upload_to(transport: Transport, session: Session, data: bytes, resumed: bool) -> StoredFile:
    base = f"{BASE}/uploads/{session.upload_id}"
    size = session.chunk_size
    parts = [data[o : o + size] for o in range(0, len(data), size)]
    etags: dict[int, str] = {}

    if resumed:
        try:
            held = _call(transport, "GET", f"{base}/parts")
        except ApiError as e:
            if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
                raise _Expired from None
            raise
        for p in held["parts"]:
            n = p["part"]
            if 1 <= n <= len(parts) and p["size"] == len(parts[n - 1]) and p["checksum"] == _part_checksum(parts[n - 1]):
                etags[n] = p["etag"]

    def send(n: int) -> None:
        part = parts[n - 1]
        r = _checked(transport, "PUT", f"{base}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
        etags[n] = r["etag"]

    for n in range(1, len(parts) + 1):
        if n not in etags:
            send(n)

    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    checksum = f"{hashlib.sha256(digests).hexdigest()}-{len(parts)}"
    retried = False
    while True:
        body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
        r = transport.send("POST", f"{base}/commit", {}, body)
        if r.status in (200, 201):
            return _stored(json.loads(r.body))
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
        except (ValueError, KeyError, TypeError):
            error, code = {}, ""
        if r.status == 410 and code == "upload_expired":
            raise _Expired
        if r.status == 409 and code == "parts_missing" and not retried:
            retried = True
            for n in sorted(set(error.get("missing") or [])):
                send(n)
            continue
        raise ApiError(r.status, code)

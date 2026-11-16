"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
RESUME_MARGIN = 600
PLANS = {  # smallest chunk, largest chunk
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
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
            missing = list(err.get("missing", []))
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
    while True:
        try:
            if resume:
                current = session
            else:
                current = _start(transport, name, len(data), chunk)
                if record is not None:
                    record(current)
            return _run(transport, current, data, resume)
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
                resume = False
                continue
            raise


def _chunk_size(plan: str, size: int) -> int:
    lo, hi = PLANS[plan.strip().lower()]
    if size >= hi:
        return hi
    unit = 64 * KIB
    return max(lo, -(-size // unit) * unit)


def _start(transport: Transport, name: str, size: int, chunk: int) -> Session:
    s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk})
    return Session(s["upload_id"], s["chunk_size"], s["expires_at"])


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _put(transport: Transport, upload_id: str, n: int, part: bytes) -> str:
    r = _call(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
    return r["etag"]


def _run(transport: Transport, s: Session, data: bytes, resume: bool) -> StoredFile:
    size = s.chunk_size
    parts = [data[o : o + size] for o in range(0, len(data), size)]
    etags: dict[int, str] = {}
    if resume:
        listed = _call(transport, "GET", f"{BASE}/uploads/{s.upload_id}/parts")
        have = {p["part"]: p for p in listed["parts"]}
        for n, part in enumerate(parts, 1):
            h = have.get(n)
            if h is not None and h["size"] == len(part) and h["checksum"] == _part_checksum(part):
                etags[n] = h["etag"]
    for n, part in enumerate(parts, 1):
        if n not in etags:
            etags[n] = _put(transport, s.upload_id, n, part)
    digests = b"".join(hashlib.sha256(p).digest() for p in parts)
    checksum = base64.urlsafe_b64encode(hashlib.sha256(digests).digest()).decode().rstrip("=") + f"-{len(parts)}"
    commit = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
    path = f"{BASE}/uploads/{s.upload_id}/commit"
    try:
        return _stored(_call(transport, "POST", path, commit))
    except ApiError as e:
        if e.status != 409 or e.code != "parts_missing":
            raise
        missing = sorted(e.missing)
    for n in missing:
        etags[n] = _put(transport, s.upload_id, n, parts[n - 1])
    commit["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
    return _stored(_call(transport, "POST", path, commit))

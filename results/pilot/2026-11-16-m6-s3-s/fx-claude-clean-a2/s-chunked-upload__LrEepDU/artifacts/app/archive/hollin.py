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
# plan -> (smallest chunk, largest chunk)
_PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),  # old name of team
    "business": (256 * KIB, 2 * MIB),
}
RESUME_MARGIN = 600


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
    smallest, largest = _PLANS[plan.strip().lower()]
    if len(data) >= largest:
        chunk = largest
    else:
        chunk = max(smallest, -(-len(data) // (64 * KIB)) * 64 * KIB)

    replaced = False

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        new = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(new)
        return new

    current: Session | None = None
    received: dict[int, dict[str, Any]] = {}
    if session is not None and session.expires_at - transport.now() > RESUME_MARGIN:
        try:
            listing = _call(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
            current = session
            received = {p["part"]: p for p in listing["parts"]}
        except ApiError as e:
            if not ((e.status == 410 and e.code == "upload_expired") or (e.status == 404 and e.code == "not_found")):
                raise
            replaced = True
    while True:
        if current is None:
            current = start()
            received = {}
        try:
            return _send_and_commit(transport, data, current, received)
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
                current = None
                continue
            raise


def _send_and_commit(transport: Transport, data: bytes, s: Session, received: dict[int, dict[str, Any]]) -> StoredFile:
    size = s.chunk_size
    parts = [data[o : o + size] for o in range(0, len(data), size)]
    digests = [hashlib.sha256(p).digest() for p in parts]
    sums = ["sha256=" + base64.b64encode(d).decode("ascii") for d in digests]
    etags: dict[int, str] = {}
    base = f"{BASE}/uploads/{s.upload_id}"

    def put(n: int) -> None:
        r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": sums[n - 1]})
        etags[n] = r["etag"]

    for n in range(1, len(parts) + 1):
        have = received.get(n)
        if have is not None and have.get("size") == len(parts[n - 1]) and have.get("checksum") == sums[n - 1]:
            etags[n] = have["etag"]
        else:
            put(n)
    file_sum = base64.urlsafe_b64encode(hashlib.sha256(b"".join(digests)).digest()).decode("ascii").rstrip("=") + f"-{len(parts)}"
    retried = False
    while True:
        body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": file_sum}
        r = transport.send("POST", f"{base}/commit", {}, body)
        if r.status in (200, 201):
            return _stored(json.loads(r.body))
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
        except (ValueError, KeyError, TypeError):
            err, code = {}, ""
        if r.status == 409 and code == "parts_missing" and not retried:
            retried = True
            for n in sorted(err.get("missing") or []):
                put(n)
            continue
        raise ApiError(r.status, code)

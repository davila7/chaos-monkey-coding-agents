"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
CHUNK = 1024 * 1024


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
        err = ApiError(r.status, code)
        try:
            err.missing = [int(x) for x in json.loads(r.body)["error"]["missing"]]
        except (ValueError, KeyError, TypeError):
            err.missing = []
        raise err
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
    replaced = False

    def start() -> Session:
        size = largest
        if len(data) < largest:
            size = max(smallest, -(-len(data) // _KIB64) * _KIB64)
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": size})
        new = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(new)
        return new

    current = session
    resume = session is not None and session.expires_at > transport.now() + 600
    if not resume:
        current = start()
    while True:
        try:
            return _run(transport, data, current, resume)
        except ApiError as e:
            gone = e.status == 410 and e.code == "upload_expired"
            if not gone or replaced:
                raise
            replaced = True
            current = start()
            resume = False


_KIB64 = 64 * 1024
_PLANS = {
    "free": (64 * 1024, 256 * 1024),
    "team": (64 * 1024, 512 * 1024),
    "pro": (64 * 1024, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
}


def _limits(plan: str) -> tuple[int, int]:
    return _PLANS[plan.strip().lower()]


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


def _run(transport: Transport, data: bytes, session: Session, resume: bool) -> StoredFile:
    chunk = session.chunk_size
    parts = [data[o : o + chunk] for o in range(0, len(data), chunk)]
    base = f"{BASE}/uploads/{session.upload_id}"
    etags: dict[int, str] = {}

    def send(n: int) -> None:
        r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": _part_checksum(parts[n - 1])})
        etags[n] = r["etag"]

    if resume:
        try:
            held = _call(transport, "GET", f"{base}/parts")
        except ApiError as e:
            if e.status in (404, 410) and e.code in ("upload_expired", "not_found"):
                e.status, e.code = 410, "upload_expired"
            raise
        have = {h["part"]: h for h in held["parts"]}
        for n in range(1, len(parts) + 1):
            h = have.get(n)
            if h and h["size"] == len(parts[n - 1]) and h["checksum"] == _part_checksum(parts[n - 1]):
                etags[n] = h["etag"]
            else:
                send(n)
    else:
        for n in range(1, len(parts) + 1):
            send(n)

    def commit() -> StoredFile:
        body = {
            "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
            "checksum": _file_checksum(parts),
        }
        return _stored(_call(transport, "POST", f"{base}/commit", body))

    try:
        return commit()
    except ApiError as e:
        if not (e.status == 409 and e.code == "parts_missing"):
            raise
        missing = e.missing
    for n in sorted(missing):
        send(n)
    return commit()

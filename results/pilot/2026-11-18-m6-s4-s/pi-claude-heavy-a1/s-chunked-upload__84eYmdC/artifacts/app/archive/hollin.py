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
            err.missing = list(json.loads(r.body)["error"]["missing"])
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


KIB = 1024
_PLANS = {  # smallest chunk, largest chunk
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = _PLANS[key]
    if size >= hi:
        return hi
    need = -(-size // (64 * KIB)) * (64 * KIB)
    return max(lo, need)


def _b64(d: bytes) -> str:
    return base64.b64encode(d).decode()


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
    listing_phase = False

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
        st = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(st)
        return st

    def parts_of(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    cur = None
    resumed = False
    if session is not None and session.expires_at - transport.now() > 600:
        cur = session
        resumed = True
    if cur is None:
        cur = start()

    while True:
        try:
            parts = parts_of(cur.chunk_size)
            digests = [hashlib.sha256(p).digest() for p in parts]
            sums = ["sha256=" + _b64(d) for d in digests]
            etags: dict[int, str] = {}
            if resumed:
                listing_phase = True
                listing = _call(transport, "GET", f"{BASE}/uploads/{cur.upload_id}/parts")
                for h in listing["parts"]:
                    n = h["part"]
                    if 1 <= n <= len(parts) and h["size"] == len(parts[n - 1]) and h["checksum"] == sums[n - 1]:
                        etags[n] = h["etag"]
                listing_phase = False
                resumed = False

            def send(n: int) -> None:
                r = _call(transport, "PUT", f"{BASE}/uploads/{cur.upload_id}/parts/{n}", parts[n - 1], {"Part-Checksum": sums[n - 1]})
                etags[n] = r["etag"]

            for n in range(1, len(parts) + 1):
                if n not in etags:
                    send(n)
            fchk = base64.urlsafe_b64encode(hashlib.sha256(b"".join(digests)).digest()).decode().rstrip("=") + f"-{len(parts)}"

            def commit() -> StoredFile:
                body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": fchk}
                return _stored(_call(transport, "POST", f"{BASE}/uploads/{cur.upload_id}/commit", body))

            try:
                return commit()
            except ApiError as e:
                if e.status != 409 or e.code != "parts_missing":
                    raise
                for n in sorted(e.missing):
                    send(n)
                return commit()
        except ApiError as e:
            gone = (e.status == 410 and e.code == "upload_expired") or (
                listing_phase and e.status == 404 and e.code == "not_found"
            )
            if not gone or replaced:
                raise
            replaced = True
            cur = start()

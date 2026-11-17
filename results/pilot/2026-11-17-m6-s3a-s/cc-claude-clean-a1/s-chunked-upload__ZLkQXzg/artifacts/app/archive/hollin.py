"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
# plan -> (smallest chunk, largest chunk)
PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
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
        err = ApiError(r.status, code)
        try:
            err.missing = [int(n) for n in json.loads(r.body)["error"]["missing"]]
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


def _chunk_size(plan: str, size: int) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    smallest, largest = PLANS[key]
    if size >= largest:
        return largest
    fitting = -(-size // (64 * KIB)) * (64 * KIB)
    return max(smallest, fitting)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


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
    resume = session is not None and session.expires_at - transport.now() > RESUME_MARGIN
    current = session if resume else None

    while True:
        try:
            held: dict[int, str] = {}  # part number -> etag known to be held
            if current is None:
                size = len(data)
                chunk = _chunk_size(plan, size)
                s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk})
                current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
                if record is not None:
                    record(current)
                resumed = False
            else:
                resumed = True
            chunk = current.chunk_size
            parts = [data[o : o + chunk] for o in range(0, len(data), chunk)]
            digests = [hashlib.sha256(p).digest() for p in parts]
            checksums = ["sha256=" + _b64(d) for d in digests]
            base = f"{BASE}/uploads/{current.upload_id}"

            if resumed:
                try:
                    listing = _call(transport, "GET", f"{base}/parts")
                except ApiError as e:
                    if e.status == 404 and e.code == "not_found":
                        raise ApiError(410, "upload_expired") from e
                    raise
                for item in listing["parts"]:
                    n = item["part"]
                    if 1 <= n <= len(parts) and item["size"] == len(parts[n - 1]) and item["checksum"] == checksums[n - 1]:
                        held[n] = item["etag"]

            def send(n: int) -> None:
                r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": checksums[n - 1]})
                held[n] = r["etag"]

            for n in range(1, len(parts) + 1):
                if n not in held:
                    send(n)

            file_checksum = base64.urlsafe_b64encode(hashlib.sha256(b"".join(digests)).digest()).decode().rstrip("=") + f"-{len(parts)}"
            retried = False
            while True:
                commit = {"parts": [{"part": n, "etag": held[n]} for n in range(1, len(parts) + 1)], "checksum": file_checksum}
                try:
                    return _stored(_call(transport, "POST", f"{base}/commit", commit))
                except ApiError as e:
                    if e.status == 409 and e.code == "parts_missing" and not retried:
                        retried = True
                        for n in sorted(set(e.missing)):
                            if 1 <= n <= len(parts):
                                send(n)
                        continue
                    raise
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" and not replaced:
                replaced = True
                current = None
                continue
            raise

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


class _Gone(Exception):
    pass


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        error = ApiError(r.status, code)
        try:
            error.missing = [int(n) for n in json.loads(r.body)["error"]["missing"]]
        except (ValueError, KeyError, TypeError):
            error.missing = []
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
    KIB = 1024
    limits = {"free": (64 * KIB, 256 * KIB), "team": (64 * KIB, 512 * KIB), "business": (256 * KIB, 2048 * KIB)}
    key = plan.strip().lower()
    smallest, largest = limits["team" if key == "pro" else key]
    if len(data) >= largest:
        chunk_size = largest
    else:
        blocks = -(-len(data) // (64 * KIB))
        chunk_size = min(max(blocks * 64 * KIB, smallest), largest)

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk_size})
        new = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(new)
        return new

    def attempt(active: Session, resumed: bool) -> StoredFile:
        size = active.chunk_size
        parts = [data[offset : offset + size] for offset in range(0, len(data), size)]
        digests = [hashlib.sha256(part).digest() for part in parts]
        checksums = ["sha256=" + base64.b64encode(digest).decode() for digest in digests]
        etags: dict[int, str] = {}
        base = f"{BASE}/uploads/{active.upload_id}"

        def put(number: int) -> None:
            r = _call(transport, "PUT", f"{base}/parts/{number}", parts[number - 1], {"Part-Checksum": checksums[number - 1]})
            etags[number] = r["etag"]

        if resumed:
            try:
                held = _call(transport, "GET", f"{base}/parts")["parts"]
            except ApiError as error:
                if (error.status, error.code) in ((410, "upload_expired"), (404, "not_found")):
                    raise _Gone() from error
                raise
            for entry in held:
                number = entry["part"]
                if 1 <= number <= len(parts) and entry["size"] == len(parts[number - 1]) and entry["checksum"] == checksums[number - 1]:
                    etags[number] = entry["etag"]
        for number in range(1, len(parts) + 1):
            if number not in etags:
                put(number)
        file_checksum = base64.urlsafe_b64encode(hashlib.sha256(b"".join(digests)).digest()).decode().rstrip("=") + f"-{len(parts)}"

        def commit() -> StoredFile:
            body = {"parts": [{"part": number, "etag": etags[number]} for number in range(1, len(parts) + 1)], "checksum": file_checksum}
            return _stored(_call(transport, "POST", f"{base}/commit", body))

        try:
            return commit()
        except ApiError as error:
            if error.status != 409 or error.code != "parts_missing":
                raise
            missing = error.missing
        for number in sorted(missing):
            put(number)
        return commit()

    replaced = False
    if session is not None and session.expires_at > transport.now() + 600:
        active, resumed = session, True
    else:
        active, resumed = start(), False
    while True:
        try:
            return attempt(active, resumed)
        except (ApiError, _Gone) as error:
            if isinstance(error, ApiError) and (error.status, error.code) != (410, "upload_expired"):
                raise
            if replaced:
                raise error.__cause__ if isinstance(error, _Gone) else error
            replaced = True
            active, resumed = start(), False

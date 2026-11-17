"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
# plan -> (smallest chunk, largest chunk); "pro" is the old name of "team".
PLAN_CHUNKS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
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
    return _upload(transport, name, data, plan, session, record)


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLAN_CHUNKS[plan.strip().lower()]
    if size >= largest:
        return largest
    unit = 64 * KIB
    fit = -(-size // unit) * unit
    return max(fit, smallest)


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode("ascii")


def _file_checksum(parts: list[bytes]) -> str:
    digests = [hashlib.sha256(p).digest() for p in parts]
    whole = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(whole).decode("ascii").rstrip("=") + f"-{len(parts)}"


def _error(r: Response) -> tuple[ApiError, list[int]]:
    code = ""
    missing: list[int] = []
    try:
        err = json.loads(r.body)["error"]
        code = str(err["code"])
        missing = [int(n) for n in err.get("missing", [])]
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return ApiError(r.status, code), missing


def _expired(e: ApiError) -> bool:
    return e.status == 410 and e.code == "upload_expired"


def _upload(
    transport: Transport,
    name: str,
    data: bytes,
    plan: str,
    saved: Session | None,
    record: Callable[[Session], None] | None,
) -> StoredFile:
    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    def attempt(s: Session, resumed: bool) -> StoredFile:
        base = f"{BASE}/uploads/{s.upload_id}"
        parts = [data[o : o + s.chunk_size] for o in range(0, len(data), s.chunk_size)]
        checksums = [_part_checksum(p) for p in parts]
        etags: dict[int, str] = {}
        if resumed:
            try:
                held = _call(transport, "GET", f"{base}/parts")
            except ApiError as e:
                if e.status == 404 and e.code == "not_found":
                    raise ApiError(410, "upload_expired") from None
                raise
            for h in held["parts"]:
                n = h["part"]
                if 1 <= n <= len(parts) and h["size"] == len(parts[n - 1]) and h["checksum"] == checksums[n - 1]:
                    etags[n] = h["etag"]
                else:
                    etags.pop(n, None)

        def send(n: int) -> None:
            r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": checksums[n - 1]})
            etags[n] = r["etag"]

        for n in range(1, len(parts) + 1):
            if n not in etags:
                send(n)
        body = {"parts": [], "checksum": _file_checksum(parts)}
        retried = False
        while True:
            body["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
            r = transport.send("POST", f"{base}/commit", {}, body)
            if r.status in (200, 201):
                return _stored(json.loads(r.body))
            err, missing = _error(r)
            if err.status == 409 and err.code == "parts_missing" and not retried:
                retried = True
                for n in sorted(set(missing)):
                    if 1 <= n <= len(parts):
                        send(n)
                continue
            raise err

    replaced = False
    s: Session | None = None
    if saved is not None and saved.expires_at - transport.now() > MIN_RESUME_SECONDS:
        try:
            return attempt(saved, True)
        except ApiError as e:
            if not _expired(e):
                raise
            replaced = True
    s = start()
    try:
        return attempt(s, False)
    except ApiError as e:
        if not _expired(e) or replaced:
            raise
    return attempt(start(), False)

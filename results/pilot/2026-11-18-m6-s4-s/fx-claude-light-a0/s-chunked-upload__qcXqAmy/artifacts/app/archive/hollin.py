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
UNIT = 64 * KIB  # chunk sizes are multiples of this
RESUME_MARGIN = 600  # seconds a saved session must still live to be resumed

# plan -> (smallest chunk, largest chunk); "pro" is the old name of "team"
PLANS = {
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "pro": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2 * MIB),
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


class _DetailedError(ApiError):
    """An ApiError that also keeps the `missing` list of a parts_missing error."""

    def __init__(self, status: int, code: str, missing: list[int]):
        super().__init__(status, code)
        self.missing = missing


def _call_detailed(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        code = ""
        missing: list[int] = []
        try:
            err = json.loads(r.body)["error"]
            code = str(err["code"])
            raw = err.get("missing")
            if isinstance(raw, list):
                missing = [int(n) for n in raw]
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        raise _DetailedError(r.status, code, missing)
    return json.loads(r.body)


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode("ascii")


def _file_checksum(digests: list[bytes]) -> str:
    whole = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(whole).decode("ascii").rstrip("=") + f"-{len(digests)}"


def _chunk_size_for(plan: str, size: int) -> int:
    try:
        smallest, largest = PLANS[plan.strip().lower()]
    except KeyError:
        raise ValueError(f"unknown plan: {plan!r}") from None
    if size >= largest:
        return largest
    fitting = -(-size // UNIT) * UNIT
    return max(smallest, fitting)


def _is_expired(e: ApiError) -> bool:
    return e.status == 410 and e.code == "upload_expired"


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
    chunk_for_new = _chunk_size_for(plan, len(data))

    def cut(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    def send_part(sess: Session, parts: list[bytes], digests: list[bytes], etags: dict[int, str], n: int) -> None:
        headers = {"Part-Checksum": _part_checksum(digests[n - 1])}
        r = _call_detailed(transport, "PUT", f"{BASE}/uploads/{sess.upload_id}/parts/{n}", parts[n - 1], headers)
        etags[n] = r["etag"]

    replaced = False  # whether the one replacement session has been used up
    current: Session | None = None
    etags: dict[int, str] = {}

    if session is not None and session.expires_at > transport.now() + RESUME_MARGIN:
        chunk = session.chunk_size
        parts = cut(chunk)
        digests = [hashlib.sha256(p).digest() for p in parts]
        try:
            listing = _call_detailed(transport, "GET", f"{BASE}/uploads/{session.upload_id}/parts")
        except ApiError as e:
            if not (_is_expired(e) or (e.status == 404 and e.code == "not_found")):
                raise
            replaced = True
        else:
            current = session
            held = {}
            for item in listing.get("parts", []):
                held[int(item["part"])] = item
            for n in range(1, len(parts) + 1):
                item = held.get(n)
                if item is not None and item.get("size") == len(parts[n - 1]) and item.get("checksum") == _part_checksum(digests[n - 1]):
                    etags[n] = item["etag"]

    while True:
        try:
            if current is None:
                chunk = chunk_for_new
                s = _call_detailed(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
                current = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
                etags = {}
                if record is not None:
                    record(current)
            chunk = current.chunk_size
            parts = cut(chunk)
            digests = [hashlib.sha256(p).digest() for p in parts]
            for n in range(1, len(parts) + 1):
                if n not in etags:
                    send_part(current, parts, digests, etags, n)
            retried = False
            while True:
                commit = {
                    "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
                    "checksum": _file_checksum(digests),
                }
                try:
                    return _stored(_call_detailed(transport, "POST", f"{BASE}/uploads/{current.upload_id}/commit", commit))
                except _DetailedError as e:
                    if e.status != 409 or e.code != "parts_missing" or retried:
                        raise
                    retried = True
                    for n in sorted(set(e.missing)):
                        if 1 <= n <= len(parts):
                            send_part(current, parts, digests, etags, n)
        except ApiError as e:
            if not _is_expired(e) or replaced:
                raise
            replaced = True
            current = None
            etags = {}

"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"
KIB = 1024
PLANS = {  # plan: (smallest chunk, largest chunk)
    "free": (64 * KIB, 256 * KIB),
    "team": (64 * KIB, 512 * KIB),
    "business": (256 * KIB, 2048 * KIB),
}
PLANS["pro"] = PLANS["team"]
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


def _error_object(r: Response) -> dict[str, Any]:
    try:
        err = json.loads(r.body)["error"]
    except (ValueError, KeyError, TypeError):
        return {}
    return err if isinstance(err, dict) else {}


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        raise ApiError(r.status, str(_error_object(r).get("code", "")))
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


def _chunk_size(plan: str, size: int) -> int:
    smallest, largest = PLANS[plan.strip().lower()]
    wanted = -(-size // (64 * KIB)) * (64 * KIB)
    return min(largest, max(smallest, wanted))


class _Expired(Exception):
    pass


def _expired(e: ApiError) -> bool:
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

    def split(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    def send_part(upload_id: str, n: int, part: bytes) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
        return r["etag"]

    def run(upload_id: str, parts: list[bytes], etags: dict[int, str]) -> StoredFile:
        for n, part in enumerate(parts, 1):
            if n not in etags:
                etags[n] = send_part(upload_id, n, part)
        checksum = _file_checksum(parts)
        retried = False
        while True:
            body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": checksum}
            r = transport.send("POST", f"{BASE}/uploads/{upload_id}/commit", {}, body)
            if r.status in (200, 201):
                return _stored(json.loads(r.body))
            err = _error_object(r)
            code = str(err.get("code", ""))
            if r.status == 409 and code == "parts_missing" and not retried:
                retried = True
                for n in sorted(err.get("missing", [])):
                    etags[n] = send_part(upload_id, n, parts[n - 1])
                continue
            raise ApiError(r.status, code)

    def fresh() -> StoredFile:
        chunk = _chunk_size(plan, len(data))
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return run(started.upload_id, split(started.chunk_size), {})

    def resume(saved: Session) -> StoredFile:
        parts = split(saved.chunk_size)
        try:
            listing = _call(transport, "GET", f"{BASE}/uploads/{saved.upload_id}/parts")
        except ApiError as e:
            if e.status == 404 and e.code == "not_found":
                raise _Expired from e
            raise
        etags: dict[int, str] = {}
        for held in listing["parts"]:
            n = held["part"]
            if 1 <= n <= len(parts) and held["size"] == len(parts[n - 1]) and held["checksum"] == _part_checksum(parts[n - 1]):
                etags[n] = held["etag"]
        return run(saved.upload_id, parts, etags)

    def attempt(fn: Callable[[], StoredFile]) -> StoredFile | None:
        try:
            return fn()
        except _Expired:
            return None
        except ApiError as e:
            if _expired(e):
                return None
            raise

    resumed = session is not None and session.expires_at - transport.now() > MIN_RESUME_SECONDS
    if resumed:
        done = attempt(lambda: resume(session))
        if done is not None:
            return done
    done = attempt(fresh)
    if done is not None:
        return done
    # A call starts at most one replacement session; a first session that expired uses it up.
    if resumed:
        raise ApiError(410, "upload_expired")
    done = attempt(fresh)
    if done is None:
        raise ApiError(410, "upload_expired")
    return done

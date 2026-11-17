"""Client for the Hollin Files API."""

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple, Protocol

BASE = "/v3"


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


class _Missing(ApiError):
    missing: list[int] = []


def _call(transport: Transport, method: str, path: str, body: bytes | dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = transport.send(method, path, headers or {}, body)
    if r.status not in (200, 201):
        try:
            code = str(json.loads(r.body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        if r.status == 409 and code == "parts_missing":
            m = _Missing(r.status, code)
            try:
                m.missing = [int(x) for x in json.loads(r.body)["error"]["missing"]]
            except (ValueError, KeyError, TypeError):
                m.missing = []
            raise m
        raise ApiError(r.status, code)
    return json.loads(r.body)


_KIB64 = 64 * 1024
_PLANS = {  # smallest chunk, largest chunk
    "free": (_KIB64, 256 * 1024),
    "team": (_KIB64, 512 * 1024),
    "business": (256 * 1024, 2 * 1024 * 1024),
}


def _limits(plan: str) -> tuple[int, int]:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    smallest, largest = _PLANS[key]
    return largest, smallest


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    h = hashlib.sha256(b"".join(hashlib.sha256(x).digest() for x in parts)).digest()
    return base64.urlsafe_b64encode(h).decode().rstrip("=") + f"-{len(parts)}"


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
    largest, smallest = _limits(plan)
    total = len(data)
    if total >= largest:
        chunk = largest
    else:
        chunk = max(smallest, -(-total // _KIB64) * _KIB64)

    def parts_of(size: int) -> list[bytes]:
        return [data[o : o + size] for o in range(0, total, size)]

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": total, "chunk_size": chunk})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    def put(upload_id: str, n: int, part: bytes) -> str:
        r = _call(transport, "PUT", f"{BASE}/uploads/{upload_id}/parts/{n}", part, {"Part-Checksum": _part_checksum(part)})
        return r["etag"]

    def run(sess: Session, resumed: bool) -> StoredFile:
        uid = sess.upload_id
        parts = parts_of(sess.chunk_size)
        sums = [_part_checksum(x) for x in parts]
        etags: dict[int, str] = {}
        if resumed:
            try:
                got = _call(transport, "GET", f"{BASE}/uploads/{uid}/parts")
            except ApiError as e:
                e.on_listing = True  # type: ignore[attr-defined]
                raise
            for h in got.get("parts", []):
                n = h["part"]
                if 1 <= n <= len(parts) and h["size"] == len(parts[n - 1]) and h["checksum"] == sums[n - 1]:
                    etags[n] = h["etag"]
        for n, part in enumerate(parts, 1):
            if n not in etags:
                etags[n] = put(uid, n, part)
        body = {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": _file_checksum(parts)}
        try:
            return _stored(_call(transport, "POST", f"{BASE}/uploads/{uid}/commit", body))
        except _Missing as e:
            for n in sorted(e.missing):
                etags[n] = put(uid, n, parts[n - 1])
            body["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
            return _stored(_call(transport, "POST", f"{BASE}/uploads/{uid}/commit", body))

    replaced = False
    if session is not None and session.expires_at - transport.now() > 600:
        try:
            return run(session, True)
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired" or (e.status == 404 and e.code == "not_found" and getattr(e, "on_listing", False)):
                replaced = True
            else:
                raise
    try:
        return run(start(), False)
    except ApiError as e:
        if replaced or not (e.status == 410 and e.code == "upload_expired"):
            raise
    return run(start(), False)

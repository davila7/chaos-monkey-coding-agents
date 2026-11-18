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
    KIB = 1024
    limits = {"free": (64 * KIB, 256 * KIB), "team": (64 * KIB, 512 * KIB), "business": (256 * KIB, 2048 * KIB)}
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    lo, hi = limits[key]

    def new_chunk() -> int:
        if len(data) >= hi:
            return hi
        need = max(-(-len(data) // (64 * KIB)) * 64 * KIB, lo)
        return min(need, hi)

    def split(chunk: int) -> list[bytes]:
        return [data[o : o + chunk] for o in range(0, len(data), chunk)]

    def pchecksum(part: bytes) -> str:
        return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()

    def fchecksum(parts: list[bytes]) -> str:
        h = hashlib.sha256(b"".join(hashlib.sha256(x).digest() for x in parts)).hexdigest()
        return f"{h}-{len(parts)}"

    def put(up: str, parts: list[bytes], n: int, etags: dict[int, str]) -> None:
        r = _call(transport, "PUT", f"{BASE}/uploads/{up}/parts/{n}", parts[n - 1], {"Part-Checksum": pchecksum(parts[n - 1])})
        etags[n] = r["etag"]

    def run(sess: Session, resumed: bool) -> StoredFile:
        up = sess.upload_id
        parts = split(sess.chunk_size)
        etags: dict[int, str] = {}
        if resumed:
            try:
                got = _call(transport, "GET", f"{BASE}/uploads/{up}/parts")
            except ApiError as e:
                if e.status == 404 and e.code == "not_found":
                    raise ApiError(410, "upload_expired") from e
                raise
            held = {p["part"]: p for p in got["parts"]}
            for n in range(1, len(parts) + 1):
                h = held.get(n)
                if h and h["size"] == len(parts[n - 1]) and h["checksum"] == pchecksum(parts[n - 1]):
                    etags[n] = h["etag"]
            todo = [n for n in range(1, len(parts) + 1) if n not in etags]
        else:
            todo = list(range(1, len(parts) + 1))
        for n in todo:
            put(up, parts, n, etags)
        body = {"parts": None, "checksum": fchecksum(parts)}
        for attempt in range(2):
            body["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
            try:
                return _stored(_call(transport, "POST", f"{BASE}/uploads/{up}/commit", dict(body)))
            except ApiError as e:
                if e.status == 409 and e.code == "parts_missing" and attempt == 0:
                    missing = list(getattr(e, "missing", []))
                    for n in sorted(missing):
                        put(up, parts, n, etags)
                    continue
                raise
        raise AssertionError

    def start() -> Session:
        chunk = new_chunk()
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    def expired(e: ApiError) -> bool:
        return e.status == 410 and e.code == "upload_expired"

    cur = None
    resumed = False
    if session is not None and session.expires_at > transport.now() + 600:
        cur, resumed = session, True
    replaced = False
    while True:
        if cur is None:
            cur = start()
        try:
            return run(cur, resumed)
        except ApiError as e:
            if not expired(e) or replaced:
                raise
            replaced = True
            cur, resumed = None, False

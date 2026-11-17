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
# plan -> (smallest chunk, largest chunk, largest file)
PLANS = {
    "free": (64 * KIB, 256 * KIB, 4 * MIB),
    "team": (64 * KIB, 512 * KIB, 64 * MIB),
    "business": (256 * KIB, 2 * MIB, 1024 * MIB),
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
        error: dict[str, Any] = {}
        try:
            error = json.loads(r.body)["error"]
            code = str(error["code"])
        except (ValueError, KeyError, TypeError):
            code = ""
        exc = ApiError(r.status, code)
        exc.missing = error.get("missing", []) if isinstance(error, dict) else []  # type: ignore[attr-defined]
        raise exc
    return json.loads(r.body)


def _stored(f: dict[str, Any]) -> StoredFile:
    return StoredFile(f["file_id"], f["name"], f["size"], f["checksum"])


def file_info(transport: Transport, file_id: str) -> StoredFile:
    """The stored file with this id.

    Raises ApiError when the API answers with an error.
    """
    return _stored(_call(transport, "GET", f"{BASE}/files/{file_id}"))


def _chunk_size(plan: str) -> int:
    key = plan.strip().lower()
    if key == "pro":
        key = "team"
    return PLANS[key][1]


def _part_checksum(part: bytes) -> str:
    return "sha256=" + base64.b64encode(hashlib.sha256(part).digest()).decode()


def _file_checksum(parts: list[bytes]) -> str:
    digest = hashlib.sha256(b"".join(hashlib.sha256(p).digest() for p in parts)).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=") + f"-{len(parts)}"


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
    chunk = _chunk_size(plan)

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": chunk})
        started = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(started)
        return started

    def run(sess: Session, resumed: bool) -> StoredFile:
        size = sess.chunk_size
        parts = [data[o : o + size] for o in range(0, len(data), size)]
        sums = [_part_checksum(p) for p in parts]
        etags: dict[int, str] = {}
        if resumed:
            held = _call(transport, "GET", f"{BASE}/uploads/{sess.upload_id}/parts")
            for h in held["parts"]:
                n = h["part"]
                if 1 <= n <= len(parts) and h["size"] == len(parts[n - 1]) and h["checksum"] == sums[n - 1]:
                    etags[n] = h["etag"]

        def send(n: int) -> None:
            r = _call(transport, "PUT", f"{BASE}/uploads/{sess.upload_id}/parts/{n}", parts[n - 1], {"Part-Checksum": sums[n - 1]})
            etags[n] = r["etag"]

        for n in range(1, len(parts) + 1):
            if n not in etags:
                send(n)
        commit = {"checksum": _file_checksum(parts)}
        while True:
            commit["parts"] = [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)]
            try:
                return _stored(_call(transport, "POST", f"{BASE}/uploads/{sess.upload_id}/commit", commit))
            except ApiError as e:
                if e.status != 409 or e.code != "parts_missing":
                    raise
                for n in sorted(e.missing):  # type: ignore[attr-defined]
                    send(n)

    resumable = (
        session is not None
        and session.chunk_size == chunk
        and transport.now() < session.expires_at
    )
    if resumable:
        try:
            return run(session, True)
        except ApiError as e:
            if e.status != 410:
                raise
    try:
        return run(start(), False)
    except ApiError as e:
        if e.status != 410:
            raise
    return run(start(), False)

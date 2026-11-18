"""Client for the Hollin Files API."""

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
    import base64

    kib = 1024
    limits = {  # smallest chunk, largest chunk
        "free": (64 * kib, 256 * kib),
        "team": (64 * kib, 512 * kib),
        "pro": (64 * kib, 512 * kib),
        "business": (256 * kib, 2048 * kib),
    }
    lo, hi = limits[plan.strip().lower()]
    size = len(data)
    if size >= hi:
        chunk = hi
    else:
        chunk = max(lo, -(-size // (64 * kib)) * 64 * kib)

    def b64(b: bytes) -> str:
        return base64.b64encode(b).decode()

    class Expired(Exception):
        pass

    def call(*args: Any, **kw: Any) -> Any:
        try:
            return _call(transport, *args, **kw)
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired":
                raise Expired() from None
            raise

    def parts_of(cs: int) -> list[bytes]:
        return [data[o : o + cs] for o in range(0, size, cs)]

    def send_part(sess: Session, n: int, part: bytes) -> str:
        r = call(
            "PUT",
            f"{BASE}/uploads/{sess.upload_id}/parts/{n}",
            part,
            {"Part-Checksum": "sha256=" + b64(hashlib.sha256(part).digest())},
        )
        return r["etag"]

    def run(sess: Session, resumed: bool) -> StoredFile:
        parts = parts_of(sess.chunk_size)
        digests = [hashlib.sha256(p).digest() for p in parts]
        etags: dict[int, str] = {}
        if resumed:
            try:
                held = call("GET", f"{BASE}/uploads/{sess.upload_id}/parts")
            except ApiError as e:
                if e.status == 404 and e.code == "not_found":
                    raise Expired() from None
                raise
            for h in held["parts"]:
                n = h["part"]
                if (
                    1 <= n <= len(parts)
                    and h["size"] == len(parts[n - 1])
                    and h["checksum"] == "sha256=" + b64(digests[n - 1])
                ):
                    etags[n] = h["etag"]
        for n, part in enumerate(parts, 1):
            if n not in etags:
                etags[n] = send_part(sess, n, part)
        file_sum = (
            base64.urlsafe_b64encode(hashlib.sha256(b"".join(digests)).digest()).decode().rstrip("=")
            + f"-{len(parts)}"
        )
        path = f"{BASE}/uploads/{sess.upload_id}/commit"
        body = lambda: {"parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)], "checksum": file_sum}
        try:
            return _stored(_call(transport, "POST", path, body()))
        except ApiError as e:
            if e.status == 410 and e.code == "upload_expired":
                raise Expired() from None
            if not (e.status == 409 and e.code == "parts_missing"):
                raise
            missing = e.missing
        for n in sorted(missing):
            etags[n] = send_part(sess, n, parts[n - 1])
        return _stored(call("POST", path, body()))

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": size, "chunk_size": chunk})
        new = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(new)
        return new

    attempts = 0
    use_saved = session is not None and session.expires_at - transport.now() > 600
    while True:
        try:
            if use_saved:
                assert session is not None
                return run(session, True)
            return run(start(), False)
        except Expired:
            attempts += 1
            if attempts >= 2:
                raise ApiError(410, "upload_expired") from None
            use_saved = False

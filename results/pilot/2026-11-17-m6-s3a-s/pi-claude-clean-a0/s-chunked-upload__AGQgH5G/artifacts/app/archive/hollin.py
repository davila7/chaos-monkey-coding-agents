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
        raise ApiError(r.status, code)
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
    fit = -(-size // (64 * KIB)) * 64 * KIB
    return min(hi, max(lo, fit))


def _part_checksum(digest: bytes) -> str:
    return "sha256=" + base64.b64encode(digest).decode()


def _file_checksum(digests: list[bytes]) -> str:
    h = hashlib.sha256(b"".join(digests)).digest()
    return base64.urlsafe_b64encode(h).decode().rstrip("=") + f"-{len(digests)}"


class _Expired(Exception):
    pass


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

    def start() -> Session:
        s = _call(transport, "POST", f"{BASE}/uploads", {"name": name, "size": len(data), "chunk_size": _chunk_size(plan, len(data))})
        st = Session(s["upload_id"], s["chunk_size"], s["expires_at"])
        if record is not None:
            record(st)
        return st

    def run(sess: Session, resume: bool) -> StoredFile:
        cs = sess.chunk_size
        parts = [data[o : o + cs] for o in range(0, len(data), cs)]
        digests = [hashlib.sha256(x).digest() for x in parts]
        etags: dict[int, str] = {}
        base = f"{BASE}/uploads/{sess.upload_id}"

        def send(n: int) -> None:
            try:
                r = _call(transport, "PUT", f"{base}/parts/{n}", parts[n - 1], {"Part-Checksum": _part_checksum(digests[n - 1])})
            except ApiError as e:
                if e.status == 410 and e.code == "upload_expired":
                    raise _Expired()
                raise
            etags[n] = r["etag"]

        if resume:
            try:
                got = _call(transport, "GET", f"{base}/parts")
            except ApiError as e:
                if (e.status, e.code) in ((410, "upload_expired"), (404, "not_found")):
                    raise _Expired()
                raise
            held = {p["part"]: p for p in got["parts"]}
            for n in range(1, len(parts) + 1):
                p = held.get(n)
                if p is not None and p["size"] == len(parts[n - 1]) and p["checksum"] == _part_checksum(digests[n - 1]):
                    etags[n] = p["etag"]
                else:
                    send(n)
        else:
            for n in range(1, len(parts) + 1):
                send(n)

        retried = False
        while True:
            body = {
                "parts": [{"part": n, "etag": etags[n]} for n in range(1, len(parts) + 1)],
                "checksum": _file_checksum(digests),
            }
            try:
                return _stored(_call(transport, "POST", f"{base}/commit", body))
            except ApiError as e:
                if e.status == 410 and e.code == "upload_expired":
                    raise _Expired()
                if e.status == 409 and e.code == "parts_missing" and not retried:
                    retried = True
                    missing = _missing(transport_last[0])
                    for n in sorted(missing):
                        send(n)
                    continue
                raise

    transport_last: list[Any] = [None]
    # capture the error body of the last failed call to read `missing`
    orig_send = transport.send

    class _Wrap:
        def send(self, method, path, headers, body):
            r = orig_send(method, path, headers, body)
            transport_last[0] = r
            return r

        def now(self):
            return transport.now()

    real = transport
    transport = _Wrap()  # type: ignore[assignment]

    if session is not None and session.expires_at - real.now() > 600:
        try:
            return run(session, True)
        except _Expired:
            replaced = True
    try:
        return run(start(), False)
    except _Expired:
        if replaced:
            raise ApiError(410, "upload_expired")
    return run_replacement(run, start)


def _missing(r: Response) -> list[int]:
    try:
        return [int(x) for x in json.loads(r.body)["error"]["missing"]]
    except (ValueError, KeyError, TypeError):
        return []


def run_replacement(run, start):
    try:
        return run(start(), False)
    except _Expired:
        raise ApiError(410, "upload_expired")

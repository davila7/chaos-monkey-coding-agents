"""Client for the list endpoints of the Tidewater Freight API."""

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import NamedTuple


class Response(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


# Sends one GET request for `path` with these query parameters and returns the response.
Transport = Callable[[str, dict[str, str]], Response]


class ApiError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_all(
    transport: Transport,
    resource: str,
    filters: dict[str, str] | None = None,
    page_size: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = _utcnow,
) -> list[dict]:
    """Every item of the `resource` list endpoint that matches `filters`, in the order the API returns them.

    `page_size` is the number of items to ask for per request. None asks for the largest page
    the API accepts, and a value above that maximum is sent as the maximum.
    Every wait goes through `sleep(seconds)`; `now()` returns the current time, timezone-aware UTC.
    Raises ApiError with the response's status and error code when the API answers with an
    error the client does not retry, or when the retries allowed for a request run out.
    """
    params = dict(filters or {})
    params["page_size"] = str(page_size or 100)
    out: list[dict] = []
    while True:
        r = transport(f"/v1/{resource}", dict(params))
        if r.status != 200:
            raise ApiError(r.status, json.loads(r.body)["error"]["code"])
        page = json.loads(r.body)
        out += page["items"]
        if not page.get("next_page_token"):
            return out
        params["page_token"] = page["next_page_token"]

"""Client for the Quayline dock scheduling API."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, NamedTuple

BASE = "/v3"


class Status(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


@dataclass(frozen=True)
class Booking:
    id: str
    dock: str
    start: datetime  # timezone-aware, UTC
    duration_min: int
    carrier: str
    carrier_scac: str
    trailer: str | None
    status: Status
    cancel_reason: str | None


@dataclass(frozen=True)
class NewBooking:
    dock: str
    start: datetime  # timezone-aware, any zone
    duration_min: int
    carrier: str
    carrier_scac: str
    trailer: str | None = None


class Response(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


# Sends one request (method, path, query parameters, JSON body or None) and returns the response.
Transport = Callable[[str, str, dict[str, str], dict[str, Any] | None], Response]


class ApiError(Exception):
    """An error response: its HTTP status and the error code from its body."""

    def __init__(self, status: int, code: str):
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code


def _call(transport: Transport, method: str, path: str, params: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> Any:
    r = transport(method, path, dict(params or {}), body)
    if r.status != 200:
        try:
            code = str(json.loads(r.body)["error"])
        except (ValueError, KeyError, TypeError):
            code = ""
        raise ApiError(r.status, code)
    return json.loads(r.body)


def _booking(b: dict[str, Any]) -> Booking:
    return Booking(
        id=b["id"],
        dock=b["dock"],
        start=datetime.fromtimestamp(b["start"], timezone.utc),
        duration_min=b["duration_min"],
        carrier=b["carrier"],
        carrier_scac=b["carrier_scac"],
        trailer=b["trailer"],
        status=Status(b["status"]),
        cancel_reason=b["cancel_reason"],
    )


def get_booking(transport: Transport, booking_id: str) -> Booking:
    """The booking with this id. Raises ApiError when the API answers with an error."""
    return _booking(_call(transport, "GET", f"{BASE}/bookings/{booking_id}"))


def create_booking(transport: Transport, new: NewBooking) -> Booking:
    """Books `new` and returns the booking the API created (pending until Quayline confirms it).

    Raises ApiError when the API answers with an error, for example when the dock is taken.
    """
    body = {
        "dock": new.dock,
        "start": int(new.start.timestamp()),
        "duration_min": new.duration_min,
        "carrier": new.carrier,
        "carrier_scac": new.carrier_scac,
        "trailer": new.trailer,
    }
    return _booking(_call(transport, "POST", f"{BASE}/bookings", body=body))


def cancel_booking(transport: Transport, booking_id: str, reason: str) -> Booking:
    """Cancels the booking for `reason` and returns it as the API reports it after the cancellation.

    Raises ApiError when the API answers with an error, for example when the booking can no longer be cancelled.
    """
    return _booking(_call(transport, "POST", f"{BASE}/bookings/{booking_id}/cancel", body={"reason": reason}))


def find_bookings(transport: Transport, dock: str, day: date, status: Status | None = None) -> list[Booking]:
    """The bookings at `dock` that start on `day` (UTC), in the order the API returns them.

    With `status`, only the bookings that have that status. Raises ApiError when the API answers with an error.
    """
    params = {"date": day.strftime("%m/%d/%Y")}
    if status is not None:
        params["status"] = status.value
    page = _call(transport, "GET", f"{BASE}/docks/{dock}/bookings", params)
    return [_booking(b) for b in page["bookings"]]

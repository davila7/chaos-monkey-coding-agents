"""Loads the data directory once per command and writes the changes."""

from datetime import datetime
from functools import cached_property
from pathlib import Path

from clubroll import aliases, audit, dates, ids, members, payments
from clubroll.errors import Refused, UsageError


class Context:
    def __init__(self, data: str, by: str, now: datetime):
        self.data = Path(data)
        self.by = by
        self.now = now

    @property
    def stamp(self) -> str:
        return dates.stamp(self.now)

    @cached_property
    def members(self) -> dict[int, dict]:
        return members.load(self.data / "members.json")

    @cached_property
    def aliases(self) -> dict[int, int]:
        return aliases.load(self.data / "aliases.json")

    @cached_property
    def payments(self) -> list[dict[str, str]]:
        return payments.load(self.data / "payments.csv")

    @cached_property
    def entries(self) -> list[dict]:
        return audit.read(self.data / "audit.jsonl")

    def lookup(self, text: str) -> tuple[int, int]:
        """(number as given, number of the member it stands for) for an id on the command line."""
        n = ids.number(text)
        if n is None:
            raise UsageError("bad-id", f"not a member id: {text}")
        m = aliases.resolve(self.aliases, n)
        if m not in self.members:
            raise Refused("unknown-member", f"no member {ids.fmt(n)}")
        return n, m

    def commit(self, *, register=None, alias_map=None, payment_rows=None, new_entries=()) -> None:
        """Writes the files given, then appends the audit lines."""
        if register is not None:
            members.save(self.data / "members.json", register)
        if alias_map is not None:
            aliases.save(self.data / "aliases.json", alias_map)
        if payment_rows is not None:
            payments.save(self.data / "payments.csv", payment_rows)
        if new_entries:
            audit.append(self.data / "audit.jsonl", list(new_entries))

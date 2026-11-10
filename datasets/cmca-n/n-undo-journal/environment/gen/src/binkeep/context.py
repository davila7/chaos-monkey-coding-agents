"""Loads the data directory once per command."""

from functools import cached_property
from pathlib import Path

from binkeep import journal
from binkeep.bins import load_bins
from binkeep.items import load_items
from binkeep.store import Store


class Context:
    def __init__(self, data: str, by: str):
        self.data = Path(data)
        self.by = by

    @cached_property
    def items(self):
        return load_items(self.data / "items.csv")

    @cached_property
    def bins(self):
        return load_bins(self.data / "bins.csv")

    @cached_property
    def store(self) -> Store:
        return Store.load(self.data / "state.json", self.bins)

    @cached_property
    def entries(self) -> list[dict]:
        return journal.read(self.data / "journal.jsonl")

    def commit(self, store: Store, new_entries: list[dict]) -> None:
        journal.append(self.data / "journal.jsonl", new_entries)
        store.save()

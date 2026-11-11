"""The entry store (docs/cache.md 3 and 4)."""


class Cache:
    def __init__(self):
        self.entries: dict[str, int] = {}

    def get(self, key: str, now_ms: int) -> bool:
        """True when key holds an entry that has not expired at now_ms."""
        expires = self.entries.get(key)
        if expires is None:
            return False
        if now_ms < expires:
            return True
        del self.entries[key]
        return False

    def put(self, key: str, expires_ms: int) -> None:
        self.entries[key] = expires_ms

    def purge(self, route: str, ident: str) -> int:
        """Removes every entry of one book or author; returns how many."""
        prefix = f"{route}|{ident}|"
        doomed = [k for k in self.entries if k.startswith(prefix)]
        for k in doomed:
            del self.entries[k]
        return len(doomed)

    def flush(self) -> int:
        count = len(self.entries)
        self.entries.clear()
        return count

    def __len__(self) -> int:
        return len(self.entries)

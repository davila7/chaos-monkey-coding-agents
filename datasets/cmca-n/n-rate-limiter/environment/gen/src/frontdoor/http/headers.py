"""Request headers: an ordered list of (name, value) pairs; names compare without regard to case."""


class Headers:
    def __init__(self, pairs):
        self.pairs = [(str(n), str(v)) for n, v in pairs]

    def get(self, name: str, missing=None):
        """The value of the first header with this name."""
        low = name.lower()
        for n, v in self.pairs:
            if n.lower() == low:
                return v
        return missing

    def get_all(self, name: str) -> list:
        """The values of every header with this name, in order."""
        low = name.lower()
        return [v for n, v in self.pairs if n.lower() == low]

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None

    def __len__(self) -> int:
        return len(self.pairs)

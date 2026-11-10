"""Reads a config and its shared files into the list of assignments in the order they apply (include.md)."""

from dataclasses import dataclass

from .data import DataSet
from .errors import IncludeError, ParseError
from .lexer import parse_lines
from .values import parse_value


@dataclass(frozen=True)
class Assignment:
    section: str
    key: str
    text: str
    interp: bool
    where: str


class Loader:
    def __init__(self, ds: DataSet):
        self.ds = ds
        self.assignments: list[Assignment] = []
        self.includes: list[str] = []
        self._stack: list[str] = []

    def load(self, cid: str) -> "Loader":
        self._file(f"configs/{cid}.conf", self.ds.config_text(cid))
        return self

    def _file(self, label: str, text: str) -> str:
        if label in self._stack:
            raise IncludeError(f"{label} includes itself through {' -> '.join(self._stack)}")
        self._stack.append(label)
        section = "main"
        try:
            lines = parse_lines(text)
        except ParseError as e:
            raise ParseError(f"{label} {e}") from None
        for line in lines:
            where = f"{label} line {line.lineno}"
            if line.kind == "section":
                section = line.name
            elif line.kind == "include":
                self._include(line.name, where)
            else:
                value, interp = parse_value(line.value, where)
                self.assignments.append(Assignment(section, line.name, value, interp, where))
        self._stack.pop()
        return section

    def _include(self, name: str, where: str) -> str:
        try:
            text = self.ds.shared_text(name)
        except IncludeError as e:
            raise IncludeError(f"{where}: {e}") from None
        if name not in self.includes:
            self.includes.append(name)
        return self._file(name, text)

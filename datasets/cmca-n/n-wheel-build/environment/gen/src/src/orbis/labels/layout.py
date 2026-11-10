"""Geometry of label sheets and envelopes, and fitting address lines into a box."""

from __future__ import annotations

from dataclasses import dataclass

ELLIPSIS = "…"


@dataclass(frozen=True)
class Grid:
    page_width: float
    page_height: float
    columns: int
    rows: int
    label_width: float
    label_height: float
    padding: float
    line_height: float
    char_width: float

    @property
    def per_page(self) -> int:
        return self.columns * self.rows

    @property
    def margin_x(self) -> float:
        return (self.page_width - self.columns * self.label_width) / 2

    @property
    def margin_y(self) -> float:
        return (self.page_height - self.rows * self.label_height) / 2

    def origin(self, index: int) -> tuple[float, float]:
        """Top-left corner of label `index` on its page, filled row by row."""
        row, column = divmod(index % self.per_page, self.columns)
        return self.margin_x + column * self.label_width, self.margin_y + row * self.label_height

    def max_lines(self) -> int:
        return int((self.label_height - 2 * self.padding) // self.line_height)

    def max_chars(self) -> int:
        return int((self.label_width - 2 * self.padding) // self.char_width)


# 24 labels of 63.5 x 33.9 mm on A4, the common office sheet.
A4_24 = Grid(210.0, 297.0, 3, 8, 63.5, 33.9, 3.0, 4.2, 1.6)


@dataclass(frozen=True)
class Window:
    """An envelope with an address window."""

    width: float
    height: float
    window_x: float
    window_y: float
    window_width: float
    window_height: float
    line_height: float
    char_width: float

    def max_lines(self) -> int:
        return int(self.window_height // self.line_height)

    def max_chars(self) -> int:
        return int(self.window_width // self.char_width)


# DL envelope, window on the right as in DIN 5008 form B.
DL = Window(220.0, 110.0, 120.0, 50.0, 90.0, 45.0, 5.0, 2.0)


def fit(lines: list[str], max_lines: int, max_chars: int) -> list[str]:
    """Shortens lines to the box. When there are too many lines the middle
    ones are dropped, because the first (recipient) and the last (country or
    postcode and city) matter most to sorting machines."""
    cut = [line if len(line) <= max_chars else line[: max_chars - 1] + ELLIPSIS for line in lines]
    if len(cut) <= max_lines:
        return cut
    if max_lines <= 1:
        return cut[-1:]
    return cut[: max_lines - 1] + cut[-1:]

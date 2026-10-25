"""Plain text renderers."""

from __future__ import annotations

from orbis.postal.render.base import Item, Renderer


class TextRenderer(Renderer):
    name = "text"
    description = "one block of lines per address, blocks separated by a blank line"

    def render(self, items: list[Item]) -> str:
        if not items:
            return ""
        return "\n\n".join("\n".join(lines) for _, lines in items) + "\n"


class OneLineRenderer(Renderer):
    name = "oneline"
    description = "one line per address: the id, a tab, the lines joined by commas"

    def render(self, items: list[Item]) -> str:
        return "".join(f"{address.id}\t{', '.join(lines)}\n" for address, lines in items)

"""The envelope renderer: one DL envelope per address as SVG."""

from __future__ import annotations

from orbis.labels import layout, svg
from orbis.postal.countries import country
from orbis.postal.render.base import Item, Renderer


class EnvelopeRenderer(Renderer):
    name = "envelope"
    description = "one DL envelope per address, one SVG document each"
    window = layout.DL

    def render(self, items: list[Item]) -> str:
        env_template = svg.template("envelope.svg")
        w = self.window
        sender = ""
        if self.options.origin:
            sender = svg.text_block([f"From {country(self.options.origin).name}"], 10.0, 15.0, w.line_height, "sender")
        out = []
        for address, lines in items:
            fitted = layout.fit(lines, w.max_lines(), w.max_chars())
            body = svg.text_block(fitted, w.window_x, w.window_y + w.line_height, w.line_height, "address")
            out.append(
                env_template.substitute(
                    id=svg.escape(address.id),
                    width=svg.num(w.width),
                    height=svg.num(w.height),
                    sender=sender,
                    address=body,
                )
            )
        return "".join(out)

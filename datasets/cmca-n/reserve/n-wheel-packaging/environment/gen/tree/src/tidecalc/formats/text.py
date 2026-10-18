"""Plain text table."""

from __future__ import annotations

from tidecalc.formats.base import Format, Report
from tidecalc.timefmt import stamp


class TextFormat(Format):
    NAME = "text"
    DESCRIPTION = "aligned plain text"
    EXTENSION = ".txt"

    def render(self, report: Report) -> str:
        lines = [report.heading(), ""]
        for item in report.items:
            lines.append(f"{stamp(item.time)}  {report.kind_label(item):<16}{item.height:7.2f} m")
        if not report.items:
            lines.append(report.label("none"))
        return "\n".join(lines) + "\n"

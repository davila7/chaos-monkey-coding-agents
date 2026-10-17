"""JSON document."""

from __future__ import annotations

import json

from tidecalc import __version__
from tidecalc.formats.base import Format, Report


class JsonFormat(Format):
    NAME = "json"
    DESCRIPTION = "JSON document"
    EXTENSION = ".json"

    def render(self, report: Report) -> str:
        s = report.station
        doc = {
            "generator": f"tidecalc {__version__}",
            "station": {"id": s.id, "name": s.name, "region": s.region, "lat": s.lat, "lon": s.lon},
            "start": report.start.isoformat(),
            "days": report.days,
            "datum": report.datum,
            "items": [
                {"time": i.time.isoformat(), "kind": getattr(i, "kind", "level"), "height": round(i.height, 3)} for i in report.items
            ],
        }
        return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"

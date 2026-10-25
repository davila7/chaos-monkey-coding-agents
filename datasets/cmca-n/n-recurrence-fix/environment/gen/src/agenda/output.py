"""Event documents, the agenda listing and the text view (output.md)."""

from .events.instances import Instance, instances
from .events.model import Event
from .events.window import Window
from .timefmt import local_text, offset_text, utc_text


def instance_doc(event: Event, inst: Instance) -> dict:
    zone = event.zone
    return {
        "recurrence_id": local_text(inst.recurrence_id),
        "start": local_text(zone.to_local(inst.start_utc)),
        "end": local_text(zone.to_local(inst.end_utc)),
        "start_utc": utc_text(inst.start_utc),
        "end_utc": utc_text(inst.end_utc),
        "offset": offset_text(zone.offset_at(inst.start_utc)),
        "overridden": inst.overridden,
    }


def event_doc(event: Event, window: Window) -> dict:
    return {
        "uid": event.uid,
        "summary": event.summary,
        "zone": event.zone.name,
        "rule": event.rule.text if event.rule else None,
        "instances": [instance_doc(event, i) for i in instances(event, window)],
    }


def agenda_rows(docs: list[dict]) -> list[dict]:
    rows = [
        {"start_utc": i["start_utc"], "end_utc": i["end_utc"], "uid": d["uid"], "recurrence_id": i["recurrence_id"]}
        for d in docs
        for i in d["instances"]
    ]
    rows.sort(key=lambda r: (r["start_utc"], r["uid"], r["recurrence_id"]))
    return rows


def text_view(doc: dict) -> str:
    head = f"{doc['uid']}  {doc['summary']}  ({doc['zone']})"
    lines = [head, f"rule: {doc['rule'] or 'none'}"]
    for i in doc["instances"]:
        mark = " *" if i["overridden"] else ""
        lines.append(f"  {i['start'].replace('T', ' ')} {i['offset']}  to {i['end'].replace('T', ' ')}{mark}")
    lines.append(f"{len(doc['instances'])} instance(s)")
    return "\n".join(lines) + "\n"

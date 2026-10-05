import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from cmca_analysis.events import read_event_log, sequence_problems


def record(seq, decision="pass", **over):
    r = {
        "schema": "tt-event/2",
        "seq": seq,
        "ts": "2026-10-05T00:00:00.000Z",
        "trial_id": None,
        "task_id": "t-001",
        "attempt": 0,
        "harness": "h@1",
        "layer": "native",
        "tool_name": "Read",
        "capability": "fs.read",
        "args_hash": "b1946ac92492d234",
        "key": "9f2c1e7a40d3be55",
        "occurrence": 0,
        "decision": decision,
        "type": None,
        "payload_id": None,
        "exempt_reason": None,
        "agent_id": None,
        "latency_ms": 1.5,
        "persistence": None,
    }
    r.update(over)
    return r


def write(tmp_path: Path, records) -> Path:
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records))
    return p


def test_valid_log(tmp_path):
    recs = [record(i) for i in range(5)]
    recs.append(record(None, decision="error", error="lock timeout"))
    report = read_event_log(write(tmp_path, recs))
    assert report.ok
    assert report.error_records == 1
    assert len(report.records) == 6


def test_schema_violations_are_reported(tmp_path):
    p = write(tmp_path, [record(0), record(1, decision="maybe")])
    p.write_text(p.read_text() + "{not json\n")
    report = read_event_log(p)
    assert [lineno for lineno, _ in report.invalid] == [2, 3]
    assert not report.ok


@given(st.integers(min_value=2, max_value=200), st.data())
def test_gap_detection_finds_every_dropped_record(n, data):
    dropped = data.draw(st.sets(st.integers(min_value=0, max_value=n - 2), max_size=n - 1))
    seqs = [s for s in range(n) if s not in dropped]
    missing, dups = sequence_problems(seqs)
    assert missing == sorted(dropped)
    assert dups == []


def test_duplicates():
    assert sequence_problems([0, 1, 1, 2]) == ([], [1])

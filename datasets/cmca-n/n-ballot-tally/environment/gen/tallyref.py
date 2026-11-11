"""Ranked-choice tally, following docs/ step by step.

Usage: tallyref.py INPUT_DIR OUTPUT_FILE
"""
import csv
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

SKIP = "skip"
PASS = "pass"
OVER = "over"
RANK_COLUMN = re.compile(r"rank(\d+)")
DIRECTIVE = re.compile(r"#\s*([A-Za-z_]+)\s*:\s*(.*)")


def norm_id(text):
    return text.strip().upper()


def norm_text(text):
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text.casefold()).split())


class Contest:
    def __init__(self, spec):
        self.id = spec["id"]
        self.max_ranks = int(spec["max_ranks"])
        self.withdrawn = {norm_id(c["id"]) for c in spec["candidates"] if c["status"] == "withdrawn"}
        self.order = [norm_id(c["id"]) for c in spec["candidates"] if c["status"] != "withdrawn"]
        self.writein = {}
        for w in spec.get("write_ins", []):
            wid = norm_id(w["id"])
            self.order.append(wid)
            for name in [w["name"], *w.get("aliases", [])]:
                self.writein[norm_text(name)] = wid
        self.lot = [norm_id(c) for c in spec["lot_order"]]
        self.ballots = Counter()
        self.count = 0

    def add(self, marks):
        by_rank = {}
        for rank, kind, value in marks:
            if 1 <= rank <= self.max_ranks:
                by_rank.setdefault(rank, []).append((kind, value))
        seen = set()
        states = []
        for rank in range(1, self.max_ranks + 1):
            chosen = set()
            for kind, value in by_rank.get(rank, []):
                if kind == "write_in":
                    wid = self.writein.get(norm_text(value))
                    if wid:
                        chosen.add(wid)
                else:
                    chosen.add(norm_id(value))
            if not chosen:
                states.append(SKIP)
                continue
            chosen -= self.withdrawn
            if not chosen:
                states.append(PASS)
                continue
            fresh = chosen - seen
            seen |= chosen
            if not fresh:
                states.append(SKIP)
            elif len(fresh) > 1:
                states.append(OVER)
            else:
                states.append(fresh.pop())
        self.ballots[tuple(states)] += 1
        self.count += 1

    def choice(self, states, continuing):
        for i, s in enumerate(states):
            if s == OVER:
                return None
            if s == SKIP:
                if i + 1 < len(states) and states[i + 1] == SKIP:
                    return None
                continue
            if s == PASS:
                continue
            if s in continuing:
                return s
        return None

    def tally(self):
        continuing = list(self.order)
        rounds = []
        winner = None
        while True:
            live = set(continuing)
            tallies = {c: 0 for c in continuing}
            exhausted = 0
            for states, n in self.ballots.items():
                c = self.choice(states, live)
                if c is None:
                    exhausted += n
                else:
                    tallies[c] += n
            rec = {"round": len(rounds) + 1, "tallies": tallies, "exhausted": exhausted, "eliminated": []}
            rounds.append(rec)
            active = self.count - exhausted
            if active == 0:
                break
            leaders = [c for c in continuing if 2 * tallies[c] > active]
            if leaders:
                winner = leaders[0]
                break
            if len(continuing) == 1:
                winner = continuing[0]
                break
            zeros = [c for c in continuing if tallies[c] == 0]
            if zeros:
                out = zeros
            else:
                low = min(tallies.values())
                tied = [c for c in continuing if tallies[c] == low]
                for prev in reversed(rounds[:-1]):
                    if len(tied) == 1:
                        break
                    least = min(prev["tallies"][c] for c in tied)
                    tied = [c for c in tied if prev["tallies"][c] == least]
                if len(tied) > 1:
                    tied = [max(tied, key=self.lot.index)]
                out = tied
            rec["eliminated"] = sorted(out)
            continuing = [c for c in continuing if c not in out]
        return {"contest": self.id, "ballots": self.count, "winner": winner, "rounds": rounds}


def csv_batch(text):
    lines = text.split("\n")
    meta = {}
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
        m = DIRECTIVE.fullmatch(lines[i].strip())
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
        i += 1
    rows = list(csv.reader(io.StringIO("\n".join(lines[i:]), newline="")))
    records = []
    if rows:
        header = [h.strip() for h in rows[0]]
        for row in rows[1:]:
            if not any(f.strip() for f in row):
                continue
            fields = dict(zip(header, row))
            marks = []
            for name, value in fields.items():
                m = RANK_COLUMN.fullmatch(name)
                if not m:
                    continue
                for mark in value.split("|"):
                    mark = mark.strip()
                    if not mark:
                        continue
                    if mark.startswith("WI:"):
                        marks.append((int(m.group(1)), "write_in", mark[3:]))
                    else:
                        marks.append((int(m.group(1)), "candidate", mark))
            records.append((fields["contest"].strip(), marks))
    return meta, records


def jsonl_batch(text):
    meta = None
    records = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        obj = json.loads(line)
        if meta is None:
            meta = obj
            continue
        marks = []
        for m in obj.get("marks", []):
            if "write_in" in m:
                marks.append((int(m["rank"]), "write_in", m["write_in"]))
            else:
                marks.append((int(m["rank"]), "candidate", m["candidate"]))
        records.append((obj["contest"].strip(), marks))
    return meta or {}, records


def main(src, dst):
    src = Path(src)
    election = json.loads((src / "election.json").read_text(encoding="utf-8"))
    contests = {c["id"]: Contest(c) for c in election["contests"]}
    batches = {}
    for p in sorted((src / "cvr").iterdir()):
        if not p.is_file():
            continue
        text = p.read_bytes().decode("utf-8")
        if p.name.endswith(".csv"):
            meta, records = csv_batch(text)
        elif p.name.endswith(".jsonl"):
            meta, records = jsonl_batch(text)
        else:
            continue
        bid = str(meta["batch"]).strip()
        rev = int(str(meta["revision"]).strip())
        if bid not in batches or rev > batches[bid][0]:
            batches[bid] = (rev, str(meta["status"]).strip().lower(), records)
    for bid in sorted(batches):
        rev, status, records = batches[bid]
        if status != "final":
            continue
        for contest, marks in records:
            if contest in contests:
                contests[contest].add(marks)
    out = {"election": election["election"], "contests": [contests[c["id"]].tally() for c in election["contests"]]}
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

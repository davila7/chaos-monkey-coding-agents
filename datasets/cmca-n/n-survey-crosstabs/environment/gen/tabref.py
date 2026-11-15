"""Weighted crosstabs and response summary, following docs/ rule by rule.

Usage: tabref.py INPUT_DIR OUTPUT_FILE
"""
import csv
import io
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DELIMITERS = (",", ";", "\t")


def read_export(path):
    text = path.read_bytes().decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    first = text.split("\n", 1)[0].rstrip("\r")
    found = [d for d in DELIMITERS if d in first]
    if len(found) != 1:
        raise SystemExit(f"{path.name}: cannot tell the delimiter of the header line")
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=found[0]))
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out = []
    for row in rows[1:]:
        values = [v.strip() for v in row]
        if not any(values):
            continue
        values += [""] * (len(header) - len(values))
        out.append(dict(zip(header, values)))
    return out


def instant(text, fmt, offset):
    if fmt == "local":
        local = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        sign = -1 if offset.startswith("-") else 1
        hh, mm = offset[1:].split(":")
        moment = local.replace(tzinfo=timezone(sign * timedelta(hours=int(hh), minutes=int(mm))))
    else:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return int(moment.timestamp())


def seconds(text, fmt):
    if fmt == "clock":
        total = 0
        for part in text.split(":"):
            total = total * 60 + int(part)
        return total
    return int(text)


class Respondent:
    def __init__(self, row, version, meta, order):
        self.row = row
        self.version = version
        self.order = order
        self.id = row.get(meta["id"], "")
        self.complete = row.get(meta["status"], "") == meta["complete"]
        self.instant = instant(row.get(meta["submitted"], ""), meta["submitted_format"], meta.get("utc_offset", "+00:00"))
        self.duration = seconds(row.get(meta["duration"], ""), meta["duration_format"])
        self.last_page = int(row.get(meta["last_page"], ""))
        self.answers = {}
        self.weight = 1.0


class Question:
    def __init__(self, spec):
        self.id = spec["id"]
        self.type = spec["type"]
        self.versions = spec["versions"]
        self.ask_if = spec.get("ask_if")
        if self.type == "age":
            self.bands = spec["bands"]
            self.options = [{"code": b["code"], "label": b["label"]} for b in self.bands]
        else:
            self.options = spec["options"]
        self.missing = {o["code"] for o in self.options if o.get("missing")}
        self.exclusive = {o["code"] for o in self.options if o.get("exclusive")}
        self.shown = [o["code"] for o in self.options if not o.get("missing")]
        self.score = {o["code"]: o["score"] for o in self.options if "score" in o}

    def code(self, text, recode):
        if recode is not None:
            return recode.get(text)
        return int(text)

    def band(self, age):
        for b in self.bands:
            if b["min"] <= age <= b["max"]:
                return b["code"]
        return None

    def read(self, row, version, reference_year):
        spec = self.versions[version]
        recode = spec.get("recode")
        if self.type == "multi":
            if "columns" in spec:
                chosen = {int(code) for code, col in spec["columns"].items() if row.get(col, "") == "1"}
            else:
                text = row.get(spec["column"], "")
                chosen = {self.code(p.strip(), recode) for p in text.split(spec["separator"]) if p.strip()}
                chosen.discard(None)
            exclusive = chosen & self.exclusive
            others = chosen - self.exclusive
            if others:
                chosen = others
            elif len(exclusive) > 1:
                chosen = set()
            chosen -= self.missing
            return frozenset(chosen) if chosen else None
        text = row.get(spec["column"], "")
        if not text:
            return None
        if self.type == "age":
            source = spec["source"]
            if source == "band":
                return self.code(text, recode)
            age = int(text) if source == "age" else reference_year - int(text)
            return self.band(age)
        value = self.code(text, recode)
        if value is None or value in self.missing:
            return None
        return value

    def holds(self, answer, codes):
        if answer is None:
            return False
        if isinstance(answer, frozenset):
            return bool(answer & set(codes))
        return answer in codes


def fsum(values):
    return math.fsum(values)


def main(src, dst):
    src = Path(src)
    codebook = json.loads((src / "codebook.json").read_text(encoding="utf-8"))
    weighting = json.loads((src / "weighting.json").read_text(encoding="utf-8"))
    tables = json.loads((src / "tables.json").read_text(encoding="utf-8"))
    versions = codebook["versions"]
    questions = [Question(q) for q in codebook["questions"]]
    by_id = {q.id: q for q in questions}
    reference_year = int(codebook["reference_date"][:4])

    counts = {v: {"version": v, "rows": 0, "duplicates": 0, "short_partials": 0, "speeders": 0, "complete": 0,
                  "partial": 0} for v in versions}
    rows = []
    order = 0
    exports = src / "exports"
    for p in sorted(exports.iterdir(), key=lambda p: p.name):
        if not p.is_file() or not p.name.endswith(".csv"):
            continue
        for row in read_export(p):
            version = row.get("form_version", "")
            rows.append(Respondent(row, version, versions[version]["meta"], order))
            counts[version]["rows"] += 1
            order += 1

    best = {}
    for r in rows:
        cur = best.get(r.id)
        if cur is None or (r.complete, r.instant) > (cur.complete, cur.instant):
            best[r.id] = r
    kept = []
    for r in rows:
        if best[r.id] is r:
            kept.append(r)
        else:
            counts[r.version]["duplicates"] += 1

    after = []
    for r in kept:
        if not r.complete and r.last_page < codebook["partial_min_page"]:
            counts[r.version]["short_partials"] += 1
        else:
            after.append(r)

    medians = {}
    for v in versions:
        d = sorted(r.duration for r in after if r.complete and r.version == v)
        if d:
            mid = len(d) // 2
            medians[v] = d[mid] if len(d) % 2 else (d[mid - 1] + d[mid]) / 2
    final = []
    for r in after:
        if r.complete and r.duration * 5 < medians[r.version] * 2:
            counts[r.version]["speeders"] += 1
            continue
        final.append(r)
        counts[r.version]["complete" if r.complete else "partial"] += 1
    final.sort(key=lambda r: r.id)

    for r in final:
        for q in questions:
            spec = q.versions.get(r.version)
            asked = spec is not None and (r.complete or spec["page"] <= r.last_page)
            if asked and q.ask_if:
                asked = q.ask_if["question"] in r.answers and \
                    by_id[q.ask_if["question"]].holds(r.answers[q.ask_if["question"]], q.ask_if["codes"])
            if asked:
                r.answers[q.id] = q.read(r.row, r.version, reference_year)

    weigh(final, weighting)

    columns = [("total", None, None)]
    for qid in tables["banner"]:
        for code in by_id[qid].shown:
            columns.append((f"{qid}:{code}", qid, code))

    out_tables = []
    for t in tables["tables"]:
        q = by_id[t["question"]]
        base = [r for r in final if r.answers.get(q.id) is not None]
        cols = []
        for name, bq, bcode in columns:
            members = base if bq is None else [r for r in base if r.answers.get(bq) == bcode]
            wb = fsum(r.weight for r in members)
            values = {}
            keys = [str(c) for c in q.shown] + [n["id"] for n in t.get("nets", [])] + (["mean"] if t.get("mean") else [])
            if not members:
                values = {k: None for k in keys}
            else:
                for c in q.shown:
                    values[str(c)] = round(100 * fsum(r.weight for r in members if q.holds(r.answers[q.id], [c])) / wb, 2)
                for n in t.get("nets", []):
                    values[n["id"]] = round(100 * fsum(r.weight for r in members
                                                       if q.holds(r.answers[q.id], n["codes"])) / wb, 2)
                if t.get("mean"):
                    values["mean"] = round(fsum(r.weight * q.score[r.answers[q.id]] for r in members) / wb, 2)
            cols.append({"column": name, "base": len(members), "weighted_base": round(wb, 2), "values": values})
        out_tables.append({"table": t["id"], "columns": cols})

    weights = [r.weight for r in final]
    summary = {
        "versions": [counts[v] for v in versions],
        "respondents": len(final),
        "effective_n": round(fsum(weights) ** 2 / fsum(w * w for w in weights), 2) if weights else None,
        "weight_min": round(min(weights), 2) if weights else None,
        "weight_max": round(max(weights), 2) if weights else None,
    }
    out = {"survey": codebook["survey"], "summary": summary, "tables": out_tables}
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def weigh(people, weighting):
    if not people:
        return
    dims = []
    for d in weighting["dimensions"]:
        qid = d["question"]
        present = {r.answers.get(qid) for r in people}
        targets = {int(c): float(v) for c, v in d["targets"].items() if int(c) in present}
        total = fsum(targets.values())
        if not targets or total <= 0:
            continue
        shares = {c: v / total for c, v in targets.items()}
        groups = {c: [r for r in people if r.answers.get(qid) == c] for c in sorted(shares)}
        dims.append((shares, groups))
    for _ in range(int(weighting["max_iterations"])):
        worst = 0.0
        for shares, groups in dims:
            total = fsum(r.weight for g in groups.values() for r in g)
            for c, g in groups.items():
                f = shares[c] * total / fsum(r.weight for r in g)
                for r in g:
                    r.weight *= f
                worst = max(worst, abs(f - 1))
        if worst <= float(weighting["tolerance"]):
            break
    n = len(people)
    mean = fsum(r.weight for r in people) / n
    hi, lo = weighting["cap"] * mean, weighting["floor"] * mean
    for r in people:
        r.weight = min(max(r.weight, lo), hi)
    scale = n / fsum(r.weight for r in people)
    for r in people:
        r.weight *= scale


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

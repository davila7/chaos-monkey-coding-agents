"""Writes the codebook, weighting targets, table plan and response exports of a
residents survey fielded with three form versions.

generate(out_dir, seed, held_out=False, people=2400, offset="+01:00")

The visible set uses some of the conventions of docs/; held_out=True also
draws the others (a question routed on a multi-select answer, a region with a
target and no respondent, a third banner question, files mixing two form
versions, semicolon and tab delimiters, byte order marks, CR LF lines, padded
header names, an unfinished download). Everything depends on the arguments
only.
"""
import csv
import io
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

REFERENCE_DATE = "2027-04-01"
REGIONS = ["North", "East", "South", "West", "Central"]
BANDS = [(1, "18-29", 18, 29), (2, "30-44", 30, 44), (3, "45-64", 45, 64), (4, "65+", 65, 120)]
BAND_LABELS = {1: "18 to 29", 2: "30 to 44", 3: "45 to 64", 4: "65 or older"}
GENDERS = [(1, "Woman"), (2, "Man"), (3, "Another identity"), (9, "Prefer not to say")]
SATISFACTION = ["Very dissatisfied", "Dissatisfied", "Neither", "Satisfied", "Very satisfied"]
RATING = ["Very poor", "Poor", "Fair", "Good", "Very good"]
TRUST = ["None at all", "Not very much", "A fair amount", "A great deal"]
MODES = ["Bus", "Tram", "Train", "Ferry", "Bike share", "None of these"]
PRIORITIES = ["Housing", "Roads", "Parks", "Safety", "Schools", "Libraries", "None of these"]
PROBLEMS = ["Delays", "Crowding", "Cleanliness", "Fares", "None of these"]
PAGES = {"1": 3, "2": 4, "3": 4}


def scale(labels, dk=None):
    out = [{"code": i + 1, "label": t, "score": i + 1} for i, t in enumerate(labels)]
    if dk:
        out.append({"code": 8, "label": dk, "missing": True})
    return out


def plain(labels, exclusive_last=False):
    out = [{"code": i + 1, "label": t} for i, t in enumerate(labels)]
    if exclusive_last:
        out[-1]["exclusive"] = True
    return out


def codebook(held_out, offset, rng):
    regions = REGIONS + (["Islands"] if held_out else [])
    q = []
    q.append({"id": "region", "type": "single", "options": plain(regions), "versions": {
        "1": {"column": "Q1", "page": 1, "recode": {t: i + 1 for i, t in enumerate(regions)}},
        "2": {"column": "region", "page": 1},
        "3": {"column": "region_code", "page": 1}}})
    q.append({"id": "age_band", "type": "age",
              "bands": [{"code": c, "label": t, "min": lo, "max": hi} for c, t, lo, hi in BANDS], "versions": {
        "1": {"column": "Q2", "page": 1, "source": "band", "recode": {BAND_LABELS[c]: c for c, *_ in BANDS}},
        "2": {"column": "age", "page": 1, "source": "age"},
        "3": {"column": "birth_year", "page": 1, "source": "birth_year"}}})
    gender_opts = [{"code": c, "label": t} for c, t in GENDERS]
    gender_opts[-1]["missing"] = True
    q.append({"id": "gender", "type": "single", "options": gender_opts, "versions": {
        "1": {"column": "Q3", "page": 1, "recode": {t: c for c, t in GENDERS}},
        "2": {"column": "gender", "page": 1},
        "3": {"column": "gender", "page": 1}}})
    q.append({"id": "satisfaction", "type": "single", "options": scale(SATISFACTION, "Don't know"), "versions": {
        "1": {"column": "Q4", "page": 2, "recode": {**{t: i + 1 for i, t in enumerate(SATISFACTION)}, "Don't know": 8}},
        "2": {"column": "sat_area", "page": 2, "recode": {"1": 5, "2": 4, "3": 3, "4": 2, "5": 1, "8": 8}},
        "3": {"column": "satisfaction", "page": 2}}})
    q.append({"id": "uses_transit", "type": "single", "options": plain(["Yes", "No"]), "versions": {
        "1": {"column": "Q5", "page": 2, "recode": {"Yes": 1, "No": 2}},
        "2": {"column": "transit_user", "page": 2},
        "3": {"column": "uses_transit", "page": 2}}})
    modes = plain(MODES, exclusive_last=True) + [{"code": 99, "label": "Prefer not to say", "missing": True,
                                                  "exclusive": True}]
    q.append({"id": "transit_modes", "type": "multi", "options": modes,
              "ask_if": {"question": "uses_transit", "codes": [1]}, "versions": {
        "1": {"page": 2, "columns": {str(o["code"]): f"Q6_{o['code']}" for o in modes}},
        "2": {"column": "modes", "page": 3, "separator": "|"},
        "3": {"column": "transit_modes", "page": 3, "separator": ","}}})
    if held_out:
        q.append({"id": "transit_problems", "type": "multi", "options": plain(PROBLEMS, exclusive_last=True),
                  "ask_if": {"question": "transit_modes", "codes": [1, 2]}, "versions": {
            "2": {"column": "bus_tram_issues", "page": 3, "separator": "|"},
            "3": {"column": "transit_problems", "page": 3, "separator": ","}}})
    q.append({"id": "transit_rating", "type": "single", "options": scale(RATING, "Don't know"),
              "ask_if": {"question": "uses_transit", "codes": [1]}, "versions": {
        "2": {"column": "transit_score", "page": 3},
        "3": {"column": "transit_rating", "page": 3}}})
    q.append({"id": "priorities", "type": "multi", "options": plain(PRIORITIES, exclusive_last=True), "versions": {
        "1": {"page": 3, "columns": {str(i + 1): f"Q8_{i + 1}" for i in range(len(PRIORITIES))}},
        "2": {"column": "priorities", "page": 4, "separator": "|"},
        "3": {"column": "top_priorities", "page": 4, "separator": ";"}}})
    q.append({"id": "trust_council", "type": "single", "options": scale(TRUST, "Don't know"), "versions": {
        "1": {"column": "Q7", "page": 2},
        "2": {"column": "trust", "page": 4, "recode": {**{t: i + 1 for i, t in enumerate(TRUST)}, "Don't know": 8}},
        "3": {"column": "trust_council", "page": 4}}})
    meta = {
        "1": {"id": "ResponseId", "status": "Finished", "complete": "1", "submitted": "EndDate",
              "submitted_format": "local", "utc_offset": offset, "duration": "Duration (in seconds)",
              "duration_format": "seconds", "last_page": "LastPage"},
        "2": {"id": "respondent_id", "status": "status", "complete": "complete", "submitted": "submitted_at",
              "submitted_format": "iso", "duration": "duration_s", "duration_format": "seconds",
              "last_page": "last_page"},
        "3": {"id": "respondent_id", "status": "state", "complete": "C", "submitted": "submitted",
              "submitted_format": "iso", "duration": "elapsed", "duration_format": "clock",
              "last_page": "page_reached"},
    }
    return {"survey": "Residents survey 2027" + (" (panel B)" if held_out else ""),
            "reference_date": REFERENCE_DATE,
            "partial_min_page": 3 if held_out and rng.random() < 0.5 else 2,
            "versions": {v: {"pages": PAGES[v], "meta": meta[v]} for v in ("1", "2", "3")},
            "questions": q}


def weighting(held_out, rng):
    counts = [182400, 141250, 205900, 118300, 96150]
    if held_out:
        counts = [int(c * rng.uniform(0.8, 1.2)) for c in counts] + [15400]
    age = [19.5, 24.8, 33.1, 22.6]
    gender = [51.2, 47.9, 0.9]
    if held_out:
        age = [round(a * rng.uniform(0.85, 1.15), 1) for a in age]
    return {
        "dimensions": [
            {"question": "region", "source": "census 2026, residents 18 and older",
             "targets": {str(i + 1): c for i, c in enumerate(counts)}},
            {"question": "age_band", "source": "census 2026, percent of adults",
             "targets": {str(i + 1): a for i, a in enumerate(age)}},
            {"question": "gender", "source": "population register, percent",
             "targets": {str(i + 1): g for i, g in enumerate(gender)}},
        ],
        "max_iterations": 100,
        "tolerance": 1e-10,
        "cap": 3.5 if not held_out else 3.0,
        "floor": 0.3 if not held_out else 0.35,
    }


def table_plan(held_out):
    tables = [
        {"id": "satisfaction", "question": "satisfaction",
         "nets": [{"id": "satisfied", "codes": [4, 5]}, {"id": "dissatisfied", "codes": [1, 2]}], "mean": True},
        {"id": "uses_transit", "question": "uses_transit"},
        {"id": "transit_modes", "question": "transit_modes", "nets": [{"id": "rail", "codes": [2, 3]}]},
        {"id": "transit_rating", "question": "transit_rating", "nets": [{"id": "good", "codes": [4, 5]}],
         "mean": True},
        {"id": "priorities", "question": "priorities", "nets": [{"id": "services", "codes": [5, 6]}]},
        {"id": "trust_council", "question": "trust_council", "nets": [{"id": "trust", "codes": [3, 4]}],
         "mean": True},
    ]
    if held_out:
        tables.insert(3, {"id": "transit_problems", "question": "transit_problems"})
        tables.append({"id": "gender", "question": "gender"})
    return {"banner": ["region", "age_band"] + (["gender"] if held_out else []), "tables": tables}


class Person:
    pass


def draw_person(rng, held_out):
    p = Person()
    p.region = rng.choices([1, 2, 3, 4, 5], [30, 14, 22, 12, 22])[0]
    p.age = rng.choices([rng.randint(18, 29), rng.randint(30, 44), rng.randint(45, 64), rng.randint(65, 89)],
                        [6, 20, 40, 34])[0]
    p.gender = rng.choices([1, 2, 3, 9], [58, 38, 1.2, 2.8])[0]
    return p


def answers(rng, p, held_out):
    a = {}
    young = p.age < 30
    base = 3.4 - 0.25 * (p.region == 2) + 0.3 * (p.region == 5) - 0.35 * young + 0.2 * (p.age >= 65)
    a["satisfaction"] = 8 if rng.random() < 0.05 else min(5, max(1, round(rng.gauss(base, 1.0))))
    a["uses_transit"] = 1 if rng.random() < (0.75 if young else 0.62 if p.region in (1, 5) else 0.45) else 2
    modes = set()
    weights = [0.7, 0.35 if p.region in (1, 5) else 0.12, 0.3, 0.08 if p.region == 3 else 0.02, 0.15 + 0.2 * young]
    for i, w in enumerate(weights):
        if rng.random() < w:
            modes.add(i + 1)
    r = rng.random()
    if not modes or r < 0.04:
        modes.add(6)
    if r > 0.985:
        modes = {99}
    elif r > 0.975:
        modes = {6, 99}
    elif 0.95 < r <= 0.96:
        modes.add(99)
    a["transit_modes"] = modes
    a["transit_problems"] = {i + 1 for i, w in enumerate([0.45, 0.4, 0.2, 0.3]) if rng.random() < w} or {5}
    a["transit_rating"] = 8 if rng.random() < 0.06 else min(5, max(1, round(rng.gauss(3.1 + 0.4 * (p.region == 5), 1.1))))
    pri = set(rng.sample(range(1, 7), rng.choice([1, 2, 3, 3, 3])))
    if p.age >= 65 and rng.random() < 0.4:
        pri.add(6)
    if rng.random() < 0.03:
        pri = {7}
    elif rng.random() < 0.02:
        pri.add(7)
    a["priorities"] = pri
    a["trust_council"] = 8 if rng.random() < 0.07 else min(4, max(1, round(rng.gauss(2.4 + 0.3 * (p.age >= 65), 0.9))))
    return a


def fmt_instant(moment, version, offset, rng):
    if version == "1":
        local = moment + timedelta(seconds=offset_seconds(offset))
        return local.strftime("%Y-%m-%d %H:%M:%S")
    if version == "2":
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    shift = timedelta(hours=2) if moment >= datetime(2027, 3, 28, 1) else timedelta(hours=1)
    return (moment + shift).strftime("%Y-%m-%dT%H:%M:%S") + ("+02:00" if shift.seconds == 7200 else "+01:00")


def fmt_duration(sec, version):
    if version != "3":
        return str(sec)
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


MEDIANS = {"1": 470, "2": 610, "3": 655}
WINDOWS = {"1": (datetime(2027, 3, 1, 8), datetime(2027, 3, 12, 22)),
           "2": (datetime(2027, 3, 10, 8), datetime(2027, 3, 24, 22)),
           "3": (datetime(2027, 3, 22, 8), datetime(2027, 4, 4, 22))}


def at(rng, version, after=None):
    lo, hi = WINDOWS[version]
    if after is not None:
        lo = max(lo, after + timedelta(minutes=20))
        if lo >= hi:
            lo = hi - timedelta(hours=1)
    span = int((hi - lo).total_seconds())
    return lo + timedelta(seconds=rng.randrange(span))


def duration(rng, version, kind):
    m = MEDIANS[version]
    if kind == "speeder":
        return int(m * rng.uniform(0.15, 0.37))
    if kind == "border":
        return int(m * rng.uniform(0.42, 0.49))
    if rng.random() < 0.02:
        return int(m * rng.uniform(5.6, 14.0))
    return int(m * rng.lognormvariate(0.08, 0.28))


class Row:
    def __init__(self, pid, version, complete, moment, dur, last_page, person, ans):
        self.pid, self.version, self.complete = pid, version, complete
        self.moment, self.dur, self.last_page = moment, dur, last_page
        self.person, self.ans = person, ans
        self.prefill = False
        self.stale = False


def submissions(rng, people, held_out, offset):
    rows = []
    ids = rng.sample(range(10000, 99999), people)
    for n in range(people):
        pid = f"R{ids[n]}"
        p = draw_person(rng, held_out)
        version = rng.choices(["1", "2", "3"], [30, 40, 30])[0]
        a = answers(rng, p, held_out)
        r = rng.random()
        kind = "speeder" if r < 0.045 else "border" if r < 0.08 else "normal"
        complete = rng.random() < 0.86
        last = PAGES[version] if complete else rng.randint(1, PAGES[version] - 1)
        row = Row(pid, version, complete, at(rng, version), duration(rng, version, kind if complete else "normal"),
                  last, p, a)
        row.prefill = not complete and rng.random() < 0.35
        row.stale = rng.random() < 0.2
        rows.append(row)
        d = rng.random()
        if d < 0.035 and complete:
            later = {"1": "2", "2": "3", "3": "3"}[version]
            extra = Row(pid, later, False, at(rng, later, row.moment), duration(rng, later, "normal"),
                        rng.randint(1, PAGES[later] - 1), p, answers(rng, p, held_out))
            extra.prefill = rng.random() < 0.5
            rows.append(extra)
        elif d < 0.07 and not complete:
            later = {"1": rng.choice(["1", "2"]), "2": "2", "3": "3"}[version]
            kind2 = "speeder" if rng.random() < 0.15 else "normal"
            rows.append(Row(pid, later, True, at(rng, later, row.moment), duration(rng, later, kind2),
                            PAGES[later], p, answers(rng, p, held_out)))
        elif d < 0.1 and complete and version == "1":
            row.moment = datetime(2027, 3, 10, 10) + timedelta(seconds=rng.randrange(2 * 86400 + 10 * 3600))
            shift = offset_seconds(offset)
            gap = rng.randrange(60, abs(shift) - 60) if shift and rng.random() < 0.7 else None
            if gap is None:
                moment2 = row.moment + timedelta(seconds=rng.randrange(3 * 3600, 30 * 3600))
            else:
                moment2 = row.moment + timedelta(seconds=gap if shift > 0 else -gap)
            rows.append(Row(pid, "2", True, moment2, duration(rng, "2", "normal"), PAGES["2"], p,
                            answers(rng, p, held_out)))
        elif d < 0.11 and not complete:
            rows.append(Row(pid, version, False, at(rng, version, row.moment), duration(rng, version, "normal"),
                            rng.randint(1, PAGES[version] - 1), p, answers(rng, p, held_out)))
    return rows


def offset_seconds(offset):
    sign = -1 if offset.startswith("-") else 1
    hh, mm = offset[1:].split(":")
    return sign * (int(hh) * 3600 + int(mm) * 60)


def asked_by_page(row, page):
    return row.complete or page <= row.last_page


def cells(row, book, rng, held_out):
    """The exported cells of one row for its version."""
    v = row.version
    out = {"form_version": v}
    m = book["versions"][v]["meta"]
    out[m["id"]] = row.pid
    out[m["status"]] = m["complete"] if row.complete else {"1": "0", "2": "partial", "3": "P"}[v]
    out[m["submitted"]] = fmt_instant(row.moment, v, m.get("utc_offset", "+00:00"), rng)
    out[m["duration"]] = fmt_duration(row.dur, v)
    out[m["last_page"]] = str(row.last_page)
    p, a = row.person, row.ans
    truth = {"region": p.region, "gender": p.gender}
    truth.update(a)
    uses = a["uses_transit"] == 1
    bus_tram = uses and bool(a["transit_modes"] & {1, 2}) and not (a["transit_modes"] <= {6, 99})
    for q in book["questions"]:
        spec = q["versions"].get(v)
        if spec is None:
            continue
        shown = asked_by_page(row, spec["page"])
        routed = True
        if q["id"] in ("transit_modes", "transit_rating"):
            routed = uses
        if q["id"] == "transit_problems":
            routed = bus_tram
        write = shown and routed
        if not write and ((not shown and row.prefill) or (shown and not routed and row.stale)):
            write = rng.random() < 0.7
        if not write:
            if "columns" in spec:
                for col in spec["columns"].values():
                    out[col] = ""
            else:
                out[spec["column"]] = ""
            continue
        if rng.random() < 0.02:
            if "columns" in spec:
                for col in spec["columns"].values():
                    out[col] = "0" if v == "1" else ""
            else:
                out[spec["column"]] = ""
            continue
        qid = q["id"]
        if qid == "age_band":
            out[spec["column"]] = age_cell(p.age, spec, rng)
            continue
        if q["type"] == "multi":
            chosen = truth[qid]
            if "columns" in spec:
                for code, col in spec["columns"].items():
                    out[col] = "1" if int(code) in chosen else "0"
            else:
                codes = sorted(chosen)
                rng.shuffle(codes)
                sep = spec["separator"]
                if held_out and rng.random() < 0.2:
                    sep = f" {sep} "
                out[spec["column"]] = sep.join(str(c) for c in codes)
            continue
        code = truth[qid]
        if qid == "region" and rng.random() < 0.015:
            out[spec["column"]] = ""
            continue
        recode = spec.get("recode")
        if recode:
            text = sorted(k for k, c in recode.items() if c == code)[0]
        else:
            text = str(code)
        out[spec["column"]] = text
    return out


def age_cell(age, spec, rng):
    if spec["source"] == "band":
        for c, _, lo, hi in BANDS:
            if lo <= age <= hi:
                return BAND_LABELS[c]
    if spec["source"] == "age":
        if rng.random() < 0.012:
            return str(rng.choice([16, 17]))
        return str(age)
    if rng.random() < 0.012:
        return ""
    return str(int(REFERENCE_DATE[:4]) - age)


def columns_of(book, version):
    m = book["versions"][version]["meta"]
    cols = ["form_version", m["id"], m["status"], m["submitted"], m["duration"], m["last_page"]]
    for q in book["questions"]:
        spec = q["versions"].get(version)
        if spec is None:
            continue
        cols += list(spec["columns"].values()) if "columns" in spec else [spec["column"]]
    return cols


def render(header, rows, delimiter=",", bom=False, crlf=False, pad=False):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter, lineterminator="\r\n" if crlf else "\n")
    w.writerow([f" {h} " if pad and i % 3 == 1 else h for i, h in enumerate(header)])
    for r in rows:
        w.writerow([r.get(h, "") for h in header])
    return ("\ufeff" if bom else "") + buf.getvalue()


def union(*lists):
    out = []
    for cols in lists:
        for c in cols:
            if c not in out:
                out.append(c)
    return out


def generate(out_dir, seed, held_out=False, people=2400, offset="+01:00"):
    out = Path(out_dir)
    (out / "exports").mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    book = codebook(held_out, offset, rng)
    (out / "codebook.json").write_text(json.dumps(book, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "weighting.json").write_text(json.dumps(weighting(held_out, rng), indent=1) + "\n", encoding="utf-8")
    (out / "tables.json").write_text(json.dumps(table_plan(held_out), indent=1) + "\n", encoding="utf-8")
    rows = submissions(rng, people, held_out, offset)
    rows.sort(key=lambda r: (r.moment, r.pid))
    exported = [(r, cells(r, book, rng, held_out)) for r in rows]
    by_version = {v: [c for r, c in exported if r.version == v] for v in ("1", "2", "3")}
    split1 = datetime(2027, 3, 7)
    v1 = [(r, c) for r, c in exported if r.version == "1"]
    week1 = [c for r, c in v1 if r.moment < split1]
    week2 = [c for r, c in v1 if r.moment >= split1 - timedelta(days=1)]
    files = {}
    h1, h2, h3 = columns_of(book, "1"), columns_of(book, "2"), columns_of(book, "3")
    files["responses_v1_2027-03-07.csv"] = render(h1, week1)
    files["responses_v1_2027-03-13.csv"] = render(h1, week2, bom=held_out)
    v3 = by_version["3"]
    half = len(v3) // 2
    if not held_out:
        files["responses_v2_2027-03-25.csv"] = render(h2, by_version["2"])
        files["responses_v3_2027-03-29.csv"] = render(h3, v3[:half])
        files["responses_v3_2027-04-05.csv"] = render(h3, v3[half:])
        files["export_log.txt"] = ("export 2027-03-07 08:00 form v1 ok\nexport 2027-03-13 08:00 form v1 ok "
                                   "(re-export from 2027-03-06)\nexport 2027-03-25 08:00 form v2 ok\n"
                                   "export 2027-03-29 08:00 form v3 ok\nexport 2027-04-05 08:00 form v3 ok\n")
    else:
        v2 = by_version["2"]
        cut = len(v2) * 2 // 3
        files["responses_v2_2027-03-21.csv"] = render(h2, v2[:cut], delimiter="\t")
        mixed = sorted(v2[cut:] + v3[:half], key=lambda c: c["form_version"] + c.get("respondent_id", ""))
        rng.shuffle(mixed)
        files["responses_v2_v3_2027-03-29.csv"] = render(union(h2, h3), mixed, delimiter=";", bom=True, crlf=True,
                                                         pad=True)
        files["responses_v3_2027-04-05.csv"] = render(h3, v3[half:], crlf=True)
        late = []
        for i in range(25):
            pr = draw_person(rng, True)
            extra = Row(f"R{100000 + i}", "3", True, at(rng, "3"), duration(rng, "3", "normal"), PAGES["3"], pr,
                        answers(rng, pr, True))
            late.append(cells(extra, book, rng, True))
        files["responses_v3_2027-04-06.csv.part"] = render(h3, late)
    for name, text in files.items():
        (out / "exports" / name).write_bytes(text.encode("utf-8"))

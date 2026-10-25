"""Cross-checks the original xport module against independent readers on the held-out data set.

Usage (inside the pinned image): python3 crosscheck.py ORIG_ROOT DATA_DIR
Each format's output is read back with a parser that does not share code with
xport (csv module, json, ElementTree, sqlite3, html.parser, a TSV unescaper)
or checked against a rule computed independently (decimal rounding with the
decimal module's round(), UTC conversion with zoneinfo-free arithmetic,
column alignment by unicodedata widths). Prints counts per check.
"""

import csv
import io
import json
import re
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from xport.dataset import load  # noqa: E402
from xport.formats import export_text  # noqa: E402

DATA = Path(sys.argv[2])
counts: dict[str, list[int]] = {}


def tally(name: str, ok: bool, detail: str = "") -> None:
    c = counts.setdefault(name, [0, 0])
    c[0 if ok else 1] += 1
    if not ok and c[1] <= 3:
        print(f"MISMATCH {name}: {detail}")


def rounded(v: Decimal, scale: int, mode) -> str:
    return str(v.quantize(Decimal(1).scaleb(-scale), context=Context(prec=60, rounding=mode)))


def plain_text(col, v, fmt):
    """The text the reference should write for a value, computed from formats.md rules."""
    t = col.type
    if t == "dec":
        return rounded(v, col.scale, ROUND_HALF_UP if fmt == "xml" else ROUND_HALF_EVEN)
    if t == "datetime":
        if fmt == "xml":
            s = v.replace(microsecond=0).isoformat()
            return s.replace("+00:00", "Z") if v.tzinfo else s
        return f"{v.year:04d}-{v.month:02d}-{v.day:02d} {v.hour:02d}:{v.minute:02d}:{v.second:02d}"
    if t == "date":
        return v.isoformat()
    if t == "bool":
        return {"tsv": ("t", "f"), "fixed": ("yes", "no")}.get(fmt, ("true", "false"))[0 if v else 1]
    if t == "tags":
        return {"csv": ";", "tsv": ",", "markdown": ", "}.get(fmt, " ").join(v)
    return str(v)


def width(s: str) -> int:
    return sum(0 if unicodedata.combining(ch) else 2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


xml_bad = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")

for path in sorted(DATA.glob("*.json")):
    table = load(path)
    cols = table.columns

    # csv read back by the csv module: missing is "", empty string is "" too, so compare text.
    text = export_text(table, "csv")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    for r, row in zip(table.rows, rows[1:]):
        for c, v, got in zip(cols, r, row):
            tally("csv value", got == ("" if v is None else plain_text(c, v, "csv")), f"{c.name} {v!r} {got!r}")
    raw_lines = text.split("\r\n")
    for r, line in zip(table.rows, raw_lines[1:]):
        for c, v in zip(cols, r):
            if c.type == "str" and v == "":
                tally("csv empty string quoted", '""' in line)

    # tsv unescaped by hand.
    text = export_text(table, "tsv")
    for r, line in zip(table.rows, text.split("\n")[1:]):
        fields = line.split("\t")
        for c, v, f in zip(cols, r, fields):
            if v is None:
                tally("tsv null", f == "\\N")
                continue
            un = re.sub(r"\\(.)", lambda m: {"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}[m.group(1)], f)
            tally("tsv value", un == plain_text(c, v, "tsv"), f"{c.name} {v!r} {f!r}")

    # jsonl read by json, decimals as Decimal.
    for r, line in zip(table.rows, export_text(table, "jsonl").splitlines()):
        obj = json.loads(line, parse_float=Decimal, parse_int=Decimal)
        for c, v in zip(cols, r):
            got = obj[c.name]
            if v is None:
                tally("jsonl value", got is None)
            elif c.type == "dec":
                tally("jsonl dec unrounded", got == v and str(got) == str(v), f"{v!r} {got!r}")
            elif c.type in ("date", "datetime"):
                tally("jsonl value", datetime.fromisoformat(got) == (v if c.type == "datetime" else datetime(v.year, v.month, v.day)) if c.type == "datetime" else got == v.isoformat())
            elif c.type == "bool":
                tally("jsonl value", got is v)
            elif c.type == "int":
                tally("jsonl value", got == v)
            else:
                tally("jsonl value", got == v)
    for r, line in zip(table.rows, export_text(table, "jsonl", ["dates=epoch"]).splitlines()):
        obj = json.loads(line)
        for c, v in zip(cols, r):
            if v is None or c.type not in ("date", "datetime"):
                continue
            base = datetime(1970, 1, 1, tzinfo=timezone.utc)
            dt = datetime(v.year, v.month, v.day, tzinfo=timezone.utc) if c.type == "date" else (v if v.tzinfo else v.replace(tzinfo=timezone.utc))
            secs = (dt - base) // timedelta(seconds=1)
            tally("jsonl epoch", obj[c.name] == secs, f"{v!r} {obj[c.name]}")

    # xml read by ElementTree, both layouts.
    root = ET.fromstring(export_text(table, "xml").encode("utf-8"))
    tally("xml root name", root.get("name") == xml_bad.sub("", table.name))
    for r, el in zip(table.rows, root):
        kids = list(el)
        for c, v in zip(cols, r):
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", c.name)
            name = name if re.match(r"[A-Za-z_]", name) else "_" + name
            found = [k for k in kids if k.tag == name]
            if c.type == "tags":
                tally("xml tags", [t.text or "" for t in found[0]] == [xml_bad.sub("", t) for t in (v or [])] if found else False)
            elif v is None:
                tally("xml missing", not found)
            else:
                want = xml_bad.sub("", plain_text(c, v, "xml")).replace("\r\n", "\n").replace("\r", "\n")
                tally("xml value", found and (found[0].text or "") == want, f"{c.name} {v!r} {found and found[0].text!r}")
    root = ET.fromstring(export_text(table, "xml", ["attrs=true"]).encode("utf-8"))
    for r, el in zip(table.rows, root):
        for c, v in zip(cols, r):
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", c.name)
            name = name if re.match(r"[A-Za-z_]", name) else "_" + name
            want = None if v is None else xml_bad.sub("", plain_text(c, v, "xml"))
            tally("xml attribute", el.get(name) == want, f"{c.name} {v!r} {el.get(name)!r}")

    # sql (ansi) executed by sqlite after dropping the typed-literal keywords.
    text = export_text(table, "sql", ["batch=3"])
    if table.rows:
        db = sqlite3.connect(":memory:")
        db.execute(f'CREATE TABLE "{table.name}" (' + ", ".join('"' + c.name.replace('"', '""') + '"' for c in cols) + ")")
        db.executescript(re.sub(r"(DATE|TIMESTAMP) '", "'", text))
        got = db.execute(f'SELECT * FROM "{table.name}" ORDER BY rowid').fetchall()
        for r, g in zip(table.rows, got):
            for c, v, x in zip(cols, r, g):
                if v is None:
                    tally("sql value", x is None)
                elif c.type == "datetime":
                    u = v.astimezone(timezone.utc).replace(tzinfo=None) if v.tzinfo else v
                    tally("sql utc", x == u.strftime("%Y-%m-%d %H:%M:%S"), f"{v!r} {x!r}")
                elif c.type == "dec":
                    tally("sql dec", Decimal(str(x)) == v if "E" not in str(v).upper() else abs(Decimal(str(x)) - v) < Decimal("1e-9"))
                elif c.type == "bool":
                    tally("sql value", x == int(v))
                elif c.type == "tags":
                    tally("sql value", x == ";".join(v))
                elif c.type == "date":
                    tally("sql value", x == v.isoformat())
                else:
                    tally("sql value", x == v, f"{v!r} {x!r}")
    else:
        tally("sql empty", text == "")

    # html cells read back by html.parser.
    class Cells(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.rows, self.cur, self.cell = [], None, None

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.cur = []
            elif tag == "td":
                self.cell = []
            elif tag == "br" and self.cell is not None:
                self.cell.append("\n")

        def handle_endtag(self, tag):
            if tag == "td":
                self.cur.append("".join(self.cell))
                self.cell = None
            elif tag == "tr" and self.cur:
                self.rows.append(self.cur)

        def handle_data(self, data):
            if self.cell is not None:
                self.cell.append(data)

    p = Cells()
    p.feed(export_text(table, "html"))
    for r, cells in zip(table.rows, p.rows):
        for c, v, got in zip(cols, r, cells):
            want = "" if v is None else ("\n".join(v) if c.type == "tags" else plain_text(c, v, "html").replace("\r\n", "\n"))
            tally("html value", got == want, f"{c.name} {v!r} {got!r}")

    # fixed: every column starts at the same terminal column on every line.
    for opts in ([], ["width=6"]):
      lines = export_text(table, "fixed", opts).splitlines()
      widths = [len(x) for x in lines[1].split("  ")] if len(lines) > 1 else []
      starts, pos = [], 0
      for w in widths:
        starts.append(pos)
        pos += w + 2
      for line in [lines[0]] + lines[2:]:
        cells_ok = True
        cut_points = starts[1:]
        segs, seg, used = [], "", 0
        for ch in line:
            if cut_points and used >= cut_points[0]:
                segs.append(seg)
                seg = ""
                cut_points = cut_points[1:]
            seg += ch
            used += 0 if unicodedata.combining(ch) else 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        segs.append(seg)
        for s in segs[:-1]:
            if not s.endswith("  "):
                cells_ok = False
        tally("fixed alignment", cells_ok, line)

for name, (good, bad) in sorted(counts.items()):
    print(f"{name}: {good} agree, {bad} differ")

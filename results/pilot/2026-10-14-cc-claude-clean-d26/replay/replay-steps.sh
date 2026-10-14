set -x
mkdir -p /app/bin /app/out; cat > /app/bin/summarize.py <<'E'
#!/usr/bin/env python3
"""Build the shipment summary described in /app/docs/summary-format.md."""
import csv
import gzip
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

KG = {
    "kg": Fraction(1),
    "g": Fraction(1, 1000),
    "lb": Fraction("0.45359237"),
    "oz": Fraction("0.028349523125"),
}
ORDER = ["central", "south", "east", "river", "north", "west", "harbor", "lakeside"]
COUNTED = {"delivered", "delivered_late"}
STATUS_CODES = {"D": "delivered", "L": "delivered_late", "C": "cancelled",
                "R": "returned", "H": "held",
                "DLV": "delivered", "DLL": "delivered_late", "CAN": "cancelled",
                "RET": "returned", "HLD": "held"}
MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}

# delimiter, columns of the depot, default decimal comma, default date form
DELIMITED = {
    "east": (",", {"id", "type", "shipped", "gross", "net", "status", "note"}, False, "YMD"),
    "lakeside": (",", {"id", "kind", "booked", "shipped", "gross_kg", "net_kg", "status"}, False, "iso"),
    "harbor": ("|", {"rec", "ref", "date", "weight", "state"}, False, "iso"),
    "river": ("\t", {"t", "ref", "shipped", "weight", "status"}, False, "MM/DD/YYYY"),
    "west": (";", {"id", "typ", "shipped", "weight", "status", "note"}, True, "DD.MM.YYYY"),
}


# ---------------------------------------------------------------- bytes/text
def read_bytes(path):
    with open(path, "rb") as f:
        b = f.read()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    return b


def decode(b):
    if b[:3] == b"\xef\xbb\xbf":
        return b[3:].decode("utf-8", "replace")
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16", "replace")[1:]
    m = re.search(rb"(?m)^#[ \t]*charset[ \t]*:[ \t]*([\w.:-]+)", b[:2000])
    if m:
        try:
            return b.decode(m.group(1).decode("ascii"))
        except (LookupError, UnicodeDecodeError):
            pass
    return b.decode("utf-8", "replace")


# -------------------------------------------------------------------- values
def parse_id(s):
    if s is None:
        return None
    m = re.fullmatch(r"\s*(?i:sh)[^0-9A-Za-z]*(\d+)\s*", s)
    return int(m.group(1)) if m else None


def norm_status(s):
    s = (s or "").strip()
    if s.upper() in STATUS_CODES:
        return STATUS_CODES[s.upper()]
    return re.sub(r"[\s\-]+", "_", s.lower())


def norm_type(s):
    s = (s or "").strip().upper()
    if s.startswith("V"):
        return "void"
    if s.startswith("C") or s.startswith("A"):
        return "correction"
    return "new"


def parse_weight(text, unit, decimal_comma):
    """Return weight in kg (Fraction) or None."""
    if text is None:
        return None
    m = re.fullmatch(r"\s*([-+]?[\d.,]*\d[\d.,]*)\s*([A-Za-z]*)\s*", str(text))
    if not m:
        return None
    num, u = m.group(1), m.group(2).lower()
    if u:
        unit = u
    if decimal_comma:
        num = num.replace(".", "").replace(",", ".")
    else:
        num = num.replace(",", "")
    if unit not in KG:
        unit = "kg"
    return Fraction(num) * KG[unit]


def parse_date(text, form):
    """Return a UTC date for a ship date or ship time."""
    t = text.strip()
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)(?::(\d\d)(?:\.\d+)?)?\s*(Z|[+-]\d\d:?\d\d)?$", t)
    if m:
        y, mo, d, h, mi, s, tz = m.groups()
        dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s or 0))
        if tz and tz != "Z":
            sign = 1 if tz[0] == "+" else -1
            digits = tz[1:].replace(":", "")
            dt -= sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        return dt.date()
    f = re.sub(r"[\s_]", "", form or "").upper()
    if f == "SERIAL" or (re.fullmatch(r"\d{5,6}(\.\d+)?", t) and f not in ("YYYYMMDD", "YYYYDDD")):
        return date(1899, 12, 30) + timedelta(days=int(float(t)))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\s+(\d{4})", t)
    if m:
        return date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    if f == "YYYYDDD":
        return date(int(t[:4]), 1, 1) + timedelta(days=int(t[4:7]) - 1)
    if f == "YYYYMMDD":
        return date(int(t[:4]), int(t[4:6]), int(t[6:8]))
    parts = [int(p) for p in re.split(r"[-/.]", t)]
    if f in ("ISO", "YMD", "YYYY-MM-DD") or parts[0] > 31:
        return date(parts[0], parts[1], parts[2])
    if f in ("MM/DD/YYYY", "MDY"):
        return date(parts[2], parts[0], parts[1])
    # DMY, DD/MM/YYYY, DD.MM.YYYY
    return date(parts[2], parts[1], parts[0])


class Rec:
    __slots__ = ("num", "type", "kg", "day", "status")

    def __init__(self, num, type_, kg=None, day=None, status=None):
        self.num, self.type, self.kg, self.day, self.status = num, type_, kg, day, status


# ------------------------------------------------------------------- readers
def logical_rows(text):
    """Yield ('comment', line) or ('row', line) honouring quoted multi-line fields."""
    buf = None
    for line in text.split("\n"):
        line = line.rstrip("\r") if buf is None else line
        if buf is None:
            if line.startswith("#"):
                yield "comment", line
                continue
            if not line.strip():
                continue
            buf = line
        else:
            buf += "\n" + line
        if buf.count('"') % 2 == 0:
            yield "row", buf
            buf = None
    if buf:
        yield "row", buf


def read_delimited(depot, text):
    delim, cols, dec_comma0, date0 = DELIMITED[depot]
    seq = None
    directives = {}
    header = None
    recs = []
    for kind, line in logical_rows(text):
        if kind == "comment":
            m = re.match(r"#\s*seq\s*=\s*(\d+)", line)
            if m and seq is None:
                seq = int(m.group(1))
            m = re.match(r"#\s*([^:=]+?)\s*:\s*(.*?)\s*$", line)
            if m:
                name = re.sub(r"\s+", " ", m.group(1).lower())
                directives[name] = m.group(2)
                if name == "seq" and seq is None and m.group(2).strip().isdigit():
                    seq = int(m.group(2))
            continue
        if delim == ",":
            fields = next(csv.reader([line]))
        else:
            fields = line.split(delim)
        if fields and all(f.strip() in cols for f in fields):
            header = [f.strip() for f in fields]
            continue
        if header is None:
            continue
        row_unit = None
        if len(fields) == len(header) + 1 and fields[-1].strip().lower() in KG:
            row_unit = fields[-1].strip().lower()
            fields = fields[:-1]
        if len(fields) < len(header):
            fields = fields + [""] * (len(header) - len(fields))
        row = dict(zip(header, fields))
        idcol = "id" if "id" in row else "ref"
        num = parse_id(row.get(idcol))
        if num is None:
            continue
        typ = norm_type(row.get("type") or row.get("kind") or row.get("typ")
                        or row.get("t") or row.get("rec"))
        if typ == "void":
            recs.append(Rec(num, typ))
            continue
        # weight
        wcol = next((c for c in ("gross", "gross_kg", "weight") if c in row), None)
        unit = None
        m = re.search(r"_(kg|g|lb|oz)$", wcol or "")
        if m:
            unit = m.group(1)
        if unit is None:
            unit = row_unit
        dir_unit = directives.get("unit") or directives.get("weight unit") or ""
        if unit is None and dir_unit:
            unit = dir_unit.split()[0].lower()
        dec_comma = dec_comma0 or "decimal comma" in dir_unit.lower()
        kg = parse_weight(row.get(wcol), unit or "kg", dec_comma)
        form = directives.get("dates") or directives.get("date format") or date0
        dcol = "date" if "date" in row else "shipped"
        try:
            day = parse_date(row[dcol], form)
        except (ValueError, KeyError, IndexError):
            day = None
        st = norm_status(row.get("status") if "status" in row else row.get("state"))
        recs.append(Rec(num, typ, kg, day, st))
    return seq, recs


FW = {
    "FW1": (42, "id", (0, 9), "type", (9, 10), "shipped", (10, 17), "weight", (17, 25), "status", (25, 26)),
    "FW2": (43, "type", (0, 1), "id", (1, 10), "shipped", (10, 18), "weight", (18, 26), "status", (26, 27)),
    "FW3": (41, "id", (0, 9), "shipped", (9, 16), "type", (16, 17), "weight", (17, 24), "status", (24, 25)),
}
FW_FORM = {"FW1": ("YYYYDDD", Fraction(1, 1000)), "FW2": ("YYYYMMDD", Fraction(1, 100)),
           "FW3": ("YYYYDDD", Fraction(1, 10) * KG["lb"])}


def read_fixed(text):
    seq = None
    layout = None
    by_len = {v[0]: k for k, v in FW.items()}
    recs = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("#"):
            m = re.match(r"#\s*LAYOUT\s+(\w+)", line, re.I)
            if m and m.group(1).upper() in FW:
                layout = m.group(1).upper()
            m = re.match(r"#\s*SEQ\s+(\d+)", line, re.I)
            if m and seq is None:
                seq = int(m.group(1))
            continue
        if not line.strip() or "\x0c" in line or re.search(r"LISTING.*PAGE", line):
            continue
        name = by_len.get(len(line))
        if name is None:
            if layout and len(line) < FW[layout][0]:
                line = line.ljust(FW[layout][0])
                name = layout
            else:
                continue
        spec = FW[name]
        f = {spec[i]: line[spec[i + 1][0]:spec[i + 1][1]] for i in range(1, len(spec), 2)}
        num = parse_id(f["id"])
        if num is None:
            continue
        typ = norm_type(f["type"])
        if typ == "void":
            recs.append(Rec(num, typ))
            continue
        form, factor = FW_FORM[name]
        try:
            day = parse_date(f["shipped"], form)
        except (ValueError, KeyError):
            day = None
        kg = int(f["weight"]) * factor
        recs.append(Rec(num, typ, kg, day, norm_status(f["status"])))
    return seq, recs


def read_xml(b):
    root = ET.fromstring(b)
    seq = root.get("seq")
    seq = int(seq) if seq and seq.strip().isdigit() else None
    root_unit = (root.get("weight-unit") or "kg").strip().lower()
    recs = []
    for el in root.iter("shipment"):
        num = parse_id(el.get("id"))
        if num is None:
            continue
        typ = norm_type(el.get("type"))
        if typ == "void":
            recs.append(Rec(num, typ))
            continue
        w = el.find("weight")
        wtext = w.text if w is not None else el.get("weight")
        unit = (w.get("unit") if w is not None else None) or el.get("weight-unit") or root_unit
        kg = parse_weight(wtext, unit.strip().lower(), False)
        s = el.find("shipped")
        stext = s.text if s is not None else el.get("shipped")
        try:
            day = parse_date(stext, "iso")
        except (ValueError, AttributeError):
            day = None
        st = el.find("status")
        recs.append(Rec(num, typ, kg, day, norm_status(st.text if st is not None else el.get("status"))))
    return seq, recs


def read_jsonl(text):
    seq = None
    meta_unit = None
    recs = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        for o in (obj if isinstance(obj, list) else [obj]):
            if not isinstance(o, dict):
                continue
            if "meta" in o and "id" not in o:
                m = o["meta"] or {}
                if seq is None and m.get("seq") is not None:
                    seq = int(m["seq"])
                meta_unit = m.get("unit") or m.get("weight_unit") or meta_unit
                continue
            num = parse_id(str(o.get("id")))
            if num is None:
                continue
            typ = norm_type(o.get("kind"))
            if typ == "void":
                recs.append(Rec(num, typ))
                continue
            kg = None
            for k, v in o.items():
                m = re.fullmatch(r"weight_(kg|g|lb|oz)", k)
                if m:
                    kg = parse_weight(str(v), m.group(1), False)
            if kg is None and "weight" in o:
                kg = parse_weight(str(o["weight"]), meta_unit or "kg", False)
            try:
                day = parse_date(o["shipped_at"], "iso")
            except (ValueError, KeyError, TypeError):
                day = None
            recs.append(Rec(num, typ, kg, day, norm_status(o.get("status"))))
    return seq, recs


def read_export(depot, path):
    b = read_bytes(path)
    if depot == "central" or b.lstrip()[:5] == b"<?xml" or b.lstrip()[:1] == b"<":
        return read_xml(b)
    text = decode(b)
    if depot == "south":
        return read_fixed(text)
    if depot == "north":
        return read_jsonl(text)
    return read_delimited(depot, text)


# ---------------------------------------------------------------------- main
def q2(x):
    d = Decimal(x.numerator) / Decimal(x.denominator) if False else None
    scaled = x * 100
    n = scaled.numerator // scaled.denominator
    rem = scaled - n
    if rem >= Fraction(1, 2):
        n += 1
    return n / 100


def main(data_dir, out_file):
    exports = {}
    for name in sorted(os.listdir(data_dir)):
        p = os.path.join(data_dir, name)
        if not os.path.isfile(p):
            continue
        depot = name.split("-", 1)[0].lower()
        seq, recs = read_export(depot, p)
        exports.setdefault(depot, []).append((seq if seq is not None else -1, name, recs))

    corrections = resends = 0
    current = {}
    for depot, items in exports.items():
        items.sort(key=lambda t: (t[0], t[1]))
        cur = {}
        for _, _, recs in items:
            for r in recs:
                if r.type == "new":
                    if r.num in cur:
                        resends += 1
                    else:
                        cur[r.num] = r
                elif r.type == "correction":
                    cur[r.num] = r
                    corrections += 1
                else:
                    cur.pop(r.num, None)
                    corrections += 1
        current[depot] = cur

    rank = {d: i for i, d in enumerate(ORDER)}
    ranked = sorted(current, key=lambda d: (rank.get(d, len(ORDER)), d))
    owners = {}
    handovers = 0
    for depot in ranked:
        for num, r in current[depot].items():
            if num in owners:
                owners[num][2] += 1
            else:
                owners[num] = [depot, r, 1]
    handovers = sum(1 for o in owners.values() if o[2] > 1)

    depots = {d: [0, Fraction(0)] for d in sorted(exports)}
    months = {}
    for depot, r, _ in owners.values():
        if r.status not in COUNTED or r.day is None or r.kg is None:
            continue
        depots[depot][0] += 1
        depots[depot][1] += r.kg
        m = months.setdefault("%04d-%02d" % (r.day.year, r.day.month), [0, Fraction(0)])
        m[0] += 1
        m[1] += r.kg

    out = {
        "depots": {d: {"shipments": v[0], "total_kg": q2(v[1])} for d, v in depots.items()},
        "months": {k: {"shipments": months[k][0], "total_kg": q2(months[k][1])} for k in sorted(months)},
        "corrections_applied": corrections,
        "resends_dropped": resends,
        "handovers": handovers,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
E
cd /app; python3 bin/summarize.py data out/summary.json && python3 tools/check_summary.py; head -30 out/summary.json
cd /app; python3 - <<'E'
import sys,glob,collections
sys.path.insert(0,'bin')
import summarize as s
for d in ('east','harbor','lakeside','river','west'):
    c=collections.Counter()
    for f in glob.glob(f'data/{d}-*'):
        t=s.decode(s.read_bytes(f))
        seq,recs=s.read_delimited(d,t)
        n=sum(1 for k,l in s.logical_rows(t) if k=='row')
        c['rows']+=n; c['recs']+=len(recs); c['nodate']+=sum(r.day is None for r in recs); c['nokg']+=sum(r.kg is None for r in recs)
        c['seqnone']+= seq is None
    print(d,c)
E
grep -ah 'TOTAL' data/east-w1.csv; grep -a -c . data/harbor-w1.psv; grep -aE '^[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|' data/harbor-w*.psv | head -3; grep -avE '^(NEW|COR|VOID)\|' data/harbor-w5.psv|head
cd /app; sed -i 's/m = re.match(r"#\\s\*seq\\s\*=\\s\*(\\d+)", line)/m = re.search(r"\\bseq\\s*=\\s*(\\d+)", line)/' bin/summarize.py; grep -n 'bseq' bin/summarize.py; python3 - <<'E'
import sys,glob,collections,csv
sys.path.insert(0,'bin')
import summarize as s
c=collections.Counter()
for f in sorted(glob.glob('data/east-*')):
    t=s.decode(s.read_bytes(f))
    for k,l in s.logical_rows(t):
        if k!='row':continue
        fl=next(csv.reader([l]))
        if s.parse_id(fl[0]) is None and not all(x in s.DELIMITED['east'][1] for x in fl):
            c[len(fl)]+=1
            if c[len(fl)]<4: print(f,fl)
        elif len(fl)>7 : print(f,fl)
print(c)
E
cd /app; python3 - <<'E'
p='bin/summarize.py'
s=open(p).read()
old=s[s.index("        row_unit = None\n"):s.index("        if len(fields) < len(header):")]
new='''        row_unit = None
        if len(fields) == len(header) + 1:
            wi = next((i for i, c in enumerate(header) if c in ("gross", "gross_kg", "weight")), None)
            cand = [i for i, f in enumerate(fields) if f.strip().lower() in KG]
            if cand:
                i = (wi + 1) if wi is not None and (wi + 1) in cand else cand[-1]
                row_unit = fields[i].strip().lower()
                fields = fields[:i] + fields[i + 1:]
'''
open(p,'w').write(s.replace(old,new))
E
python3 bin/summarize.py data out/summary.json && python3 tools/check_summary.py
cd /app; python3 - <<'E'
p='bin/summarize.py'
s=open(p).read()
old=s[s.index("        row_unit = None\n"):s.index("        if len(fields) < len(header):")]
new='''        row_unit = None
        if len(fields) == len(header) + 1:
            wi = next((i for i, c in enumerate(header) if c in ("gross", "gross_kg", "weight")), None)
            cand = [i for i, f in enumerate(fields) if f.strip().lower() in KG]
            if cand:
                i = (wi + 1) if wi is not None and (wi + 1) in cand else cand[-1]
                row_unit = fields[i].strip().lower()
                fields = fields[:i] + fields[i + 1:]
'''
open(p,'w').write(s.replace(old,new))
E
python3 bin/summarize.py data out/summary.json && python3 tools/check_summary.py
cd /app; sed -i '/d = Decimal(x.numerator)/d; /^from decimal import/d' bin/summarize.py; python3 bin/summarize.py data out/summary.json && python3 tools/check_summary.py
cat > STATUS.json <<'E'
{"status": "success", "summary": "Wrote /app/bin/summarize.py (stdlib only, rule-driven: gzip/BOM/charset, mid-file headers and directives, per-row units, fixed-width layout sniffing, seq ordering, corrections/voids/resends, handovers) and ran it on /app/data to produce /app/out/summary.json; check_summary.py reports every value matches. Behaviour on other exports is untested beyond the documented rules."}
E

"""Writes a binkeep data directory: items.csv, bins.csv, state.json, journal.jsonl.

The journal is produced by playing out a warehouse: a format 1 stretch written
by the 1.x scanners, then bins retired, then a format 2 stretch that empties
some retired bins (they are removed from bins.csv at the end when they stay
empty) and mixes operations with undo and redo entries. state.json is the
stock the journal leads to.
"""

import csv
import json
import random
from pathlib import Path

PREFIXES = ["BX", "CT", "PL", "RL", "KT", "TB", "GL", "SC", "HN", "WR"]
NOUNS = ["carton", "pallet wrap", "label roll", "tape", "glove pair", "strap", "bolt pack", "cable tie",
         "sack", "bubble roll", "corner guard", "clip", "tray", "liner", "hinge", "washer", "spacer"]
ADJECTIVES = ["small", "large", "blue", "clear", "heavy", "light", "brown", "white", "narrow", "wide"]
PACKS = [1, 1, 1, 4, 6, 10, 12, 24]
OPERATORS = ["cli", "dock-1", "dock-2", "night", "returns-desk", "scanner-07"]

DEFAULTS = {
    "items": 30,
    "zones": "ABCDEF",
    "per_zone": 7,
    "v1_ops": 70,
    "v1_tail": 25,
    "v2_ops": 60,
    "retire": 0.18,
    "delete": 3,
    "fix_v2": 0.0,
    "undo": 0.12,
    "redo": 0.8,
    "packs": 0.55,
    "typed": 0.5,
    "tail_undos": 3,
    "empty_in": "v1",
    "empty_at": 12,
}


class Floor:
    def __init__(self, rng: random.Random, opts: dict):
        self.rng = rng
        self.o = opts
        self.items = self._items()
        self.bins, self.pick = self._bins()
        self.retired: set[str] = set()
        self.closed: set[str] = set()
        self.stock: dict[str, dict[str, int]] = {}
        self.lines: list[dict] = []
        self.seq = 0
        self.done: list[dict] = []
        self.redo: list[tuple[dict, dict]] = []

    def _items(self) -> dict[str, int]:
        out: dict[str, int] = {}
        while len(out) < self.o["items"]:
            sku = f"{self.rng.choice(PREFIXES)}-{self.rng.randint(1000, 9999)}"
            out.setdefault(sku, self.rng.choice(PACKS))
        return out

    def _bins(self):
        zones = list(self.o["zones"])
        order = zones[:]
        self.rng.shuffle(order)
        codes, pick, n = [], {}, 0
        for z in order:
            racks = list(range(1, self.o["per_zone"] + 1))
            if self.rng.random() < 0.5:
                racks.reverse()
            for r in racks:
                code = f"{z}-{r:02d}"
                n += 10
                codes.append(code)
                pick[code] = n
        return sorted(codes), pick

    def qty(self, sku, b):
        return self.stock.get(sku, {}).get(b, 0)

    def put(self, sku, b, q):
        per = self.stock.setdefault(sku, {})
        if q:
            per[b] = q
        else:
            per.pop(b, None)

    def held(self, sku, active_only=False):
        bins = [b for b, q in self.stock.get(sku, {}).items() if q and not (active_only and b in self.retired)]
        return sorted(bins, key=lambda b: self.pick[b])

    def active(self):
        return [b for b in self.bins if b not in self.retired and b not in self.closed]

    def skus_with(self, active_only=False):
        return sorted(s for s in self.stock if self.held(s, active_only))

    def typed(self, b):
        r = self.rng.random()
        if r < self.o["typed"]:
            b = b.lower()
        if self.rng.random() < 0.08:
            b = " " + b if self.rng.random() < 0.5 else b + " "
        return b

    # format 1

    def v1(self, allow_irreversible=True):
        rng = self.rng
        choices = ["receive"] * 42 + ["issue"] * 22 + ["move"] * 16
        if allow_irreversible:
            choices += ["count"] * 12 + ["fix"] * 8
        op = rng.choice(choices)
        if op != "receive" and not self.skus_with(op == "issue"):
            op = "receive"
        self.seq += 1
        line = {"seq": self.seq, "op": op}
        if op == "receive":
            sku = rng.choice(sorted(self.items))
            b = rng.choice(self.active())
            pack = self.items[sku]
            line["sku"] = sku
            line["bin"] = self.typed(b)
            if pack > 1 and rng.random() < self.o["packs"]:
                n = rng.randint(1, 6)
                line["qty"] = n
                line["uom"] = "pk"
                units = n * pack
            else:
                units = rng.randint(1, 60)
                line["qty"] = units
            self.put(sku, b, self.qty(sku, b) + units)
        elif op == "issue":
            sku = rng.choice(self.skus_with(True))
            bins = self.held(sku, True)
            total = sum(self.qty(sku, b) for b in bins)
            want = rng.randint(1, min(total, 45))
            picks, left = [], want
            for b in bins:
                if not left:
                    break
                take = min(left, self.qty(sku, b))
                picks.append([self.typed(b), take])
                self.put(sku, b, self.qty(sku, b) - take)
                left -= take
            line["sku"] = sku
            line["picks"] = picks
        elif op == "move":
            sku = rng.choice(self.skus_with())
            src = rng.choice(self.held(sku))
            dst = rng.choice([b for b in self.active() if b != src])
            q = rng.randint(1, self.qty(sku, src))
            self.put(sku, src, self.qty(sku, src) - q)
            self.put(sku, dst, self.qty(sku, dst) + q)
            line.update({"sku": sku, "from": self.typed(src), "to": self.typed(dst), "qty": q})
        else:
            sku = rng.choice(self.skus_with(True))
            b = rng.choice(self.held(sku, True))
            q = max(0, self.qty(sku, b) + rng.randint(-4, 3))
            self.put(sku, b, q)
            line.update({"sku": sku, "bin": self.typed(b), "qty": q})
        self.lines.append(line)

    # format 2

    def entry(self, op, sku, effects, target=None):
        self.seq += 1
        e = {"v": 2, "seq": self.seq, "op": op, "by": self.rng.choice(OPERATORS), "sku": sku}
        if target is not None:
            e["target"] = target
        e["effects"] = effects
        self.lines.append(e)
        return e

    def change(self, sku, b, q, effects):
        effects.append({"bin": b, "before": self.qty(sku, b), "after": q})
        self.put(sku, b, q)

    def operation(self, e):
        self.redo.clear()
        self.done.append(e)

    def move2(self, sku, src, dst, q):
        effects = []
        self.change(sku, src, self.qty(sku, src) - q, effects)
        self.change(sku, dst, self.qty(sku, dst) + q, effects)
        self.operation(self.entry("move", sku, effects))

    def v2(self):
        rng = self.rng
        top = self.done[-1] if self.done else None
        if self.redo and rng.random() < self.o["redo"] * 0.4:
            t, u = self.redo.pop()
            effects = []
            for x in reversed(u["effects"]):
                self.change(t["sku"], x["bin"], x["before"], effects)
            self.entry("redo", t["sku"], effects, target=t["seq"])
            self.done.append(t)
            return
        if top is not None and top.get("v") == 2 and top["op"] != "fix" and rng.random() < self.o["undo"]:
            self.undo_top()
            return
        choices = ["receive"] * 40 + ["issue"] * 24 + ["move"] * 20 + ["count"] * 12
        op = rng.choice(choices)
        if self.o["fix_v2"] and rng.random() < self.o["fix_v2"]:
            op = "fix"
        if op != "receive" and not self.skus_with(op in ("issue", "count", "fix")):
            op = "receive"
        effects = []
        if op == "receive":
            sku = rng.choice(sorted(self.items))
            b = rng.choice(self.active())
            pack = self.items[sku]
            units = rng.randint(1, 6) * pack if pack > 1 and rng.random() < self.o["packs"] else rng.randint(1, 60)
            self.change(sku, b, self.qty(sku, b) + units, effects)
        elif op == "issue":
            sku = rng.choice(self.skus_with(True))
            bins = self.held(sku, True)
            left = rng.randint(1, min(45, sum(self.qty(sku, b) for b in bins)))
            for b in bins:
                if not left:
                    break
                take = min(left, self.qty(sku, b))
                self.change(sku, b, self.qty(sku, b) - take, effects)
                left -= take
        elif op == "move":
            sku = rng.choice(self.skus_with())
            held = self.held(sku)
            retired = [b for b in held if b in self.retired]
            src = rng.choice(retired) if retired and rng.random() < 0.5 else rng.choice(held)
            dst = rng.choice([b for b in self.active() if b != src])
            self.move2(sku, src, dst, rng.randint(1, self.qty(sku, src)))
            return
        else:
            sku = rng.choice(self.skus_with(True))
            b = rng.choice(self.held(sku, True))
            q = max(0, self.qty(sku, b) + rng.randint(-5, 3))
            self.change(sku, b, q, effects)
        e = self.entry(op, sku, effects)
        self.operation(e)

    def undo_top(self):
        t = self.done.pop()
        effects = []
        for x in reversed(t["effects"]):
            self.change(t["sku"], x["bin"], x["before"], effects)
        u = self.entry("undo", t["sku"], effects, target=t["seq"])
        self.redo.append((t, u))


def _empty(floor: Floor, rng: random.Random, n: int, v1: bool) -> list:
    """Moves all stock out of n bins that hold some; they take no stock afterwards."""
    holding = [b for b in floor.bins if b not in floor.closed and any(floor.qty(s, b) for s in floor.stock)]
    doomed = rng.sample(holding, min(n, len(holding)))
    for b in doomed:
        floor.closed.add(b)
        for sku in sorted(floor.stock):
            q = floor.qty(sku, b)
            if not q:
                continue
            dst = rng.choice(floor.active())
            if v1:
                floor.seq += 1
                floor.put(sku, b, 0)
                floor.put(sku, dst, floor.qty(sku, dst) + q)
                floor.lines.append({"seq": floor.seq, "op": "move", "sku": sku, "from": floor.typed(b), "to": floor.typed(dst), "qty": q})
            else:
                floor.move2(sku, b, dst, q)
    return doomed


def generate(out: Path, seed: int, **options) -> None:
    opts = dict(DEFAULTS, **options)
    rng = random.Random(seed)
    floor = Floor(rng, opts)
    doomed = []
    for i in range(opts["v1_ops"]):
        if opts["empty_in"] == "v1" and i == opts["v1_ops"] - opts["empty_at"]:
            doomed = _empty(floor, rng, opts["delete"], True)
        floor.v1(allow_irreversible=i < opts["v1_ops"] - opts["v1_tail"])
    holding = [b for b in floor.bins if b not in floor.closed and any(floor.qty(s, b) for s in floor.stock)]
    n_retire = max(1, round(opts["retire"] * len(floor.bins)))
    pool = holding if len(holding) >= n_retire else [b for b in floor.bins if b not in floor.closed]
    floor.retired = set(rng.sample(pool, n_retire)) | set(doomed)
    if opts["empty_in"] == "v2":
        doomed = _empty(floor, rng, opts["delete"], False)
        floor.retired |= set(doomed)
    for _ in range(opts["v2_ops"]):
        floor.v2()
    for _ in range(opts["tail_undos"]):
        top = floor.done[-1] if floor.done else None
        if top is None or top.get("v") != 2 or top["op"] == "fix":
            break
        floor.undo_top()
    gone = {b for b in doomed if not any(floor.qty(s, b) for s in floor.stock)}
    write(out, floor, gone, rng)


def write(out: Path, floor: Floor, gone: set, rng: random.Random) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "items.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["sku", "description", "pack_size"])
        for sku in sorted(floor.items):
            desc = f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}"
            w.writerow([sku, desc, floor.items[sku]])
    with open(out / "bins.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["bin", "zone", "pick_seq", "status"])
        for b in floor.bins:
            if b in gone:
                continue
            w.writerow([b, b.split("-")[0], floor.pick[b], "retired" if b in floor.retired else "active"])
    stock = {}
    for sku in sorted(floor.stock):
        held = floor.held(sku)
        if held:
            stock[sku] = {b: floor.stock[sku][b] for b in held}
    (out / "state.json").write_text(json.dumps({"format": 2, "stock": stock}, indent=2) + "\n", encoding="utf-8")
    with open(out / "journal.jsonl", "w", encoding="utf-8") as f:
        for line in floor.lines:
            if line.get("v") == 2:
                f.write(json.dumps(line, separators=(",", ":")) + "\n")
            else:
                f.write(json.dumps(line) + "\n")

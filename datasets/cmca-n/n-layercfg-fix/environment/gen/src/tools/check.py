"""Consistency checks on the documents the layercfg package resolves from a data directory.

Usage, from /app:

    python tools/check.py [--data DIR]

The tool resolves every config in DIR (./data when left out) with the package
and checks properties that every correct document has: sections and keys in
order with no template section, values whose JSON type fits their schema type,
an include list that names each shared file once, and a summary listing that
matches the documents. It prints, per rule, how many configs were checked and
how many break a property. It does not say which configs.

A document can pass every check and still be wrong: the checks read the
schema and the shared files with the package itself and never work a value
out on their own, so a value that is well formed but wrongly parsed, expanded,
converted or placed goes unnoticed. Configs the package refuses are counted on
their own line. Exit status 0 means no check failed.
"""

import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from layercfg.data import DataSet  # noqa: E402
from layercfg.errors import ConfigError  # noqa: E402
from layercfg.report import resolve, summary_rows  # noqa: E402

RULES = [
    ("output.md 2", "sections and keys in order, no template sections"),
    ("types.md", "values have the JSON type of their schema type"),
    ("include.md 4", "each included shared file listed once"),
    ("output.md 3", "summary rows match the documents and are sorted"),
]
JSON_TYPES = {"string": str, "bool": bool, "int": int, "duration": int, "size": int, "list": list}


def check_doc(doc: dict, ds: DataSet) -> set[str]:
    broken = set()
    settings = doc["settings"]
    if list(settings) != sorted(settings) or any(s.startswith("_") or not keys for s, keys in settings.items()):
        broken.add("output.md 2")
    for section, keys in settings.items():
        if list(keys) != sorted(keys):
            broken.add("output.md 2")
        for key, value in keys.items():
            type_name = ds.schema.type_of(section, key)
            want = JSON_TYPES[type_name]
            ok = isinstance(value, want) and (want is bool or not isinstance(value, bool))
            if type_name in ("duration", "size") and ok and value < 0:
                ok = False
            if type_name == "list" and ok:
                ok = all(isinstance(item, str) and item and item == item.strip() for item in value)
            if not ok:
                broken.add("types.md")
    includes = doc["includes"]
    if len(set(includes)) != len(includes) or not all((ds.root / "shared" / name).is_file() for name in includes):
        broken.add("include.md 4")
    return broken


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=str(APP / "data"))
    args = p.parse_args(argv)
    ds = DataSet(args.data)
    counts = {r: 0 for r, _ in RULES}
    checked, refused, docs = 0, 0, []
    for cid in ds.ids():
        try:
            doc = resolve(ds, cid)
        except ConfigError:
            refused += 1
            continue
        except Exception as e:  # a crash is a failed check, not a refusal
            print(f"{cid}: {type(e).__name__}: {e}")
            return 2
        checked += 1
        docs.append(doc)
        for rule in check_doc(doc, ds):
            counts[rule] += 1
    rows = summary_rows(docs)
    by_id = {d["config"]: d for d in docs}
    if [r["config"] for r in rows] != sorted(by_id) or len(rows) != len(docs):
        counts["output.md 3"] += 1
    for row in rows:
        d = by_id.get(row["config"])
        want = None if d is None else (len(d["settings"]), sum(len(v) for v in d["settings"].values()), len(d["includes"]))
        if want != (row["sections"], row["keys"], row["includes"]):
            counts["output.md 3"] += 1
    for rule, what in RULES:
        print(f"{rule:<13} {what:<52} {checked:>4} checked {counts[rule]:>4} broken")
    print(f"{'refused':<13} {'configs the package could not resolve':<52} {refused:>4}")
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())

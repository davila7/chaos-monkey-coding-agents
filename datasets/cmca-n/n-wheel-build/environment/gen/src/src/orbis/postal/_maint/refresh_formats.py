"""Checks the format files against data/countries.json and rewrites the index in canonical order.

Run from a checkout:

    python src/orbis/postal/_maint/refresh_formats.py [--write]

Every format under formats/<region>/ must have an index entry with the same
region, and every entry must have a format. Drafts under formats/_drafts/
are reported but never indexed; a draft is released by moving it into its
region directory and adding its entry by hand.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def scan() -> tuple[dict[str, str], list[str]]:
    found: dict[str, str] = {}
    drafts: list[str] = []
    for path in sorted((DATA / "formats").glob("*/*.toml")):
        region = path.parent.name
        code = tomllib.loads(path.read_text(encoding="utf-8"))["code"]
        if region == "_drafts":
            drafts.append(code)
        else:
            found[code] = region
    return found, drafts


def main(argv: list[str]) -> int:
    index_path = DATA / "countries.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = {e["code"]: e for e in index["countries"]}
    found, drafts = scan()
    problems = []
    for code, region in found.items():
        if code not in entries:
            problems.append(f"{code}: format in {region}/ has no index entry")
        elif entries[code]["region"] != region:
            problems.append(f"{code}: indexed in {entries[code]['region']}, format in {region}/")
    for code in sorted(set(entries) - set(found)):
        problems.append(f"{code}: indexed but has no format")
    for code in drafts:
        print(f"draft: {code}")
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        return 1
    if "--write" in argv:
        index["countries"] = [entries[c] for c in sorted(entries)]
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

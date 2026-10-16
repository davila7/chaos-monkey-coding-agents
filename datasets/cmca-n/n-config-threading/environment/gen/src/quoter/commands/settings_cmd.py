"""quoter settings: print the settings in effect, one per line."""

from __future__ import annotations

from dataclasses import fields

from quoter import settings


def add_parser(sub) -> None:
    p = sub.add_parser("settings", help="print the settings in effect")
    p.add_argument("names", nargs="*", metavar="NAME", help="only these settings")


def show(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return ",".join(value)
    return str(value)


def run(args, out) -> int:
    conf = settings.current()
    names = [f.name for f in fields(conf)]
    for name in args.names:
        if name not in names:
            raise settings.SettingsError(f"unknown setting {name!r}")
    for name in args.names or names:
        out.write(f"{name} = {show(getattr(conf, name))}\n")
    return 0

"""HTML rendering: a standalone page with one table per report.

Text is escaped with ``html.escape``. Amounts use the text form (-1,234.56)
inside right-aligned cells; negative amounts get the class "neg".
"""

import html

from ledger.core.money import format_amount

EXP = 2
STYLE = (
    "body{font-family:sans-serif;margin:2em}"
    "table{border-collapse:collapse;margin-bottom:2em}"
    "td,th{padding:.25em .75em;border-bottom:1px solid #ccc}"
    "td.num{text-align:right;font-variant-numeric:tabular-nums}"
    "td.neg{color:#a00}"
)


def amount_cell(cents: int) -> str:
    cls = "num neg" if cents < 0 else "num"
    return f'<td class="{cls}">{format_amount(cents, EXP, ".", ",")}</td>'


def text_cell(text: str) -> str:
    return f"<td>{html.escape(text)}</td>"


def _table(caption: str, header: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(r) + "</tr>" for r in rows)
    return f"<table><caption>{html.escape(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def monthly_table(report: dict) -> str:
    rows = [[text_cell(m), amount_cell(c)] for m, c in report["months"].items()]
    rows.append([text_cell("total"), amount_cell(report["total"])])
    return _table(f"{report['account']} ({report['currency']} -> {report['base']})", ["month", report["base"]], rows)


def vat_table(vat: dict) -> str:
    rows = [[text_cell(code), amount_cell(v["gross"]), amount_cell(v["net"]), amount_cell(v["tax"])] for code, v in vat["codes"].items()]
    rows.append([text_cell("total"), "<td></td>", "<td></td>", amount_cell(vat["total_tax"])])
    return _table(f"{vat['account']} tax ({vat['jurisdiction'] or 'no jurisdiction'})", ["code", "gross", "net", "tax"], rows)


def matrix_table(matrix: dict) -> str:
    header = ["account", "name"] + matrix["months"] + ["total"]
    rows = []
    for code, r in matrix["rows"].items():
        rows.append([text_cell(code), text_cell(r["name"])] + [amount_cell(r["months"].get(m, 0)) for m in matrix["months"]] + [amount_cell(r["total"])])
    rows.append([text_cell(""), text_cell("total")] + [amount_cell(matrix["totals"][m]) for m in matrix["months"]] + [amount_cell(matrix["total"])])
    return _table("accounts by month", header, rows)


def page(title: str, tables: list[str]) -> str:
    return (
        "<!doctype html>\n"
        f'<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{STYLE}</style></head>'
        f"<body><h1>{html.escape(title)}</h1>{''.join(tables)}</body></html>\n"
    )


def render_monthly(report: dict) -> str:
    return page(report["account"], [monthly_table(report)])


def render_vat(vat: dict) -> str:
    return page(f"{vat['account']} tax", [vat_table(vat)])

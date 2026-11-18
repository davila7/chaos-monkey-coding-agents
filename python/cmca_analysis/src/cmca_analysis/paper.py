"""`python -m cmca_analysis paper --release <dir> --out <dir>`: LaTeX numbers and tables from a release.

The paper never types a result. Every value comes from the release's `site-data.json` and
`<board>/board.json` through the macros and tables written here (D-0050 item 2), and from the
config `summary.json` files for curves, fault delivery and cost (D-0055 item 4).
"""

import argparse
import json
import re
from pathlib import Path

BOARDS = ("track-s", "track-n-fixed")
CURVE_PROFILES = ("clean", "light", "moderate", "heavy")

# Display names for the paper; a config missing here keeps its id.
HARNESS_LABELS = {
    "claude-code": "Claude Code",
    "codex": "Codex CLI",
    "fx": "fx",
    "fxh": "fxh",
    "muse": "Muse Code",
    "opencode": "OpenCode",
    "pi": "Pi",
}


def _macro_part(text: str) -> str:
    """`track-n-fixed` -> `TrackNFixed`. LaTeX macro names take letters only."""
    digits = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four",
              "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}
    words = re.split(r"[^A-Za-z0-9]+", text)
    out = "".join(w[:1].upper() + w[1:] for w in words if w)
    return "".join(digits.get(ch, ch) for ch in out)


def _fmt(value: float | None, places: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{places}f}"


def _interval(metric: dict | None, places: int = 3) -> str:
    if not metric or metric.get("value") is None:
        return "n/a"
    return f"{metric['value']:.{places}f} [{metric['lo']:.2f}, {metric['hi']:.2f}]"


def _value(metric: dict | None) -> float | None:
    return None if not metric else metric.get("value")


def _escape(text: str) -> str:
    return text.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")


def _label(row: dict) -> str:
    return HARNESS_LABELS.get(row["harness"]["name"], row["harness"]["name"])


def _sorted_rows(rows: list[dict]) -> list[dict]:
    # Home ranking order (D-0041): tasks finished under `moderate`, then id for ties.
    return sorted(rows, key=lambda r: (-r["faulted_counts"]["succeeded"], r["config_id"]))


def macros(site: dict, boards: dict[str, dict], summaries: dict[tuple[str, str], dict] | None = None) -> dict[str, str]:
    summaries = summaries or {}
    out: dict[str, str] = {"cmcaRelease": _escape(site["release"])}
    for board in site["boards"]:
        if board["id"] not in BOARDS:
            continue
        b = _macro_part(board["id"])
        rows = board["rows"]
        succeeded = [r["faulted_counts"]["succeeded"] for r in rows]
        clean = [_value(r["metrics"]["clean_pass1"]) for r in rows]
        overclaim = [v for r in rows if (v := _value(r["metrics"]["overclaim_rate"])) is not None]
        out[f"cmca{b}Configs"] = str(len(rows))
        out[f"cmca{b}SucceededMin"] = str(min(succeeded))
        out[f"cmca{b}SucceededMax"] = str(max(succeeded))
        out[f"cmca{b}CleanMin"] = _fmt(min(clean))
        out[f"cmca{b}CleanMax"] = _fmt(max(clean))
        out[f"cmca{b}OverclaimMin"] = _fmt(min(overclaim))
        out[f"cmca{b}OverclaimMax"] = _fmt(max(overclaim))
        leader = _sorted_rows(rows)[0]
        out[f"cmca{b}Leader"] = _escape(_label(leader))
        out[f"cmca{b}LeaderSucceeded"] = str(leader["faulted_counts"]["succeeded"])
        out[f"cmca{b}LeaderSent"] = str(leader["faulted_counts"]["sent"])
        last = _sorted_rows(rows)[-1]
        out[f"cmca{b}Last"] = _escape(_label(last))
        out[f"cmca{b}LastSucceeded"] = str(last["faulted_counts"]["succeeded"])
        if board.get("curve_tasks"):
            out[f"cmca{b}CurveTasks"] = str(board["curve_tasks"])
        for r in rows:
            c = b + _macro_part(r["config_id"])
            m = r["metrics"]
            for p in r.get("curve") or []:
                out[f"cmca{c}Curve{_macro_part(p['profile'])}"] = _fmt(_value(p["pass1"]))
            out[f"cmca{c}RR"] = _fmt(_value(m["rr"]))
            out[f"cmca{c}PassThree"] = _fmt(_value(m["pass3_moderate"]))
            out[f"cmca{c}Units"] = str(r["trials"])
            summary = summaries.get((board["id"], r["config_id"]))
            if summary:
                out.update(_summary_macros(c, summary))
            out[f"cmca{c}Sent"] = str(r["faulted_counts"]["sent"])
            out[f"cmca{c}Succeeded"] = str(r["faulted_counts"]["succeeded"])
            out[f"cmca{c}Excluded"] = str(r["excluded"])
            out[f"cmca{c}Clean"] = _fmt(_value(m["clean_pass1"]))
            out[f"cmca{c}Faulted"] = _fmt(_value(m["faulted_success"]))
            out[f"cmca{c}Overclaim"] = _fmt(_value(m["overclaim_rate"]))
            out[f"cmca{c}Poison"] = _fmt(_value(m["poison_propagation_rate"]))
            out[f"cmca{c}DollarsPerSuccess"] = _fmt(m.get("dollars_per_success"))
        fid_keys = [f"cmca{b}{_macro_part(r['config_id'])}Fidelity" for r in rows]
        fid = [float(out[k]) for k in fid_keys if out.get(k, "n/a") != "n/a"]
        if fid:
            out[f"cmca{b}FidelityMin"] = _fmt(min(fid))
        detail = boards.get(board["id"])
        if detail:
            comps = detail["comparisons"]
            out[f"cmca{b}Bands"] = str(len(set(detail["bands"].values())))
            out[f"cmca{b}Tasks"] = str(comps[0]["tasks"]) if comps else "n/a"
            out[f"cmca{b}MaxDifference"] = _fmt(max(abs(x["mean_difference"]) for x in comps))
            out[f"cmca{b}MinPHolm"] = _fmt(min(x["p_holm"] for x in comps), 2)
            mdd = [x["power"]["mdd"] for x in comps if x.get("power")]
            if mdd:
                out[f"cmca{b}MddMin"] = _fmt(min(mdd))
                out[f"cmca{b}MddMax"] = _fmt(max(mdd))
    return out


def _summary_macros(c: str, summary: dict) -> dict[str, str]:
    """Robustness AUC, fault delivery over every trial directory (replaced originals included) and harness-reported cost."""
    profiles = summary["profiles"].values()
    delivered = sum(p["validity"]["delivered"] for p in profiles)
    verifiable = sum(p["validity"]["delivery_verifiable"] for p in profiles)
    cost = sum(p["cost_usd_total"] or 0 for p in profiles)
    return {
        f"cmca{c}Auc": _fmt(summary.get("robustness_auc")),
        f"cmca{c}Delivered": str(delivered),
        f"cmca{c}Verifiable": str(verifiable),
        f"cmca{c}Fidelity": _fmt(delivered / verifiable if verifiable else None),
        f"cmca{c}Undeliverable": str(sum(p["validity"].get("faults_undeliverable", 0) for p in profiles)),
        f"cmca{c}Cost": f"{cost:.2f}",
    }


def curve_figure(board: dict) -> str:
    """pgfplots axis body: pass^1 against base rate per config, on the curve subset."""
    rows = [r for r in _sorted_rows(board["rows"]) if r.get("curve")]
    if not rows:
        return ""
    lines = []
    for i, r in enumerate(rows):
        pts = " ".join(f"({p['base_rate']:.2f},{_value(p['pass1']):.4f})" for p in r["curve"])
        lines.append(f"\\addplot+[mark=*, mark size=1.5pt] coordinates {{{pts}}};")
        lines.append(f"\\addlegendentry{{{_escape(_label(r))}}}")
    return "\n".join(lines) + "\n"


def detail_table(board: dict, summaries: dict[tuple[str, str], dict]) -> str:
    """Units, exclusions, fault delivery, robustness AUC and harness-reported cost per config."""
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Harness & Units & Excluded & Delivered / verifiable & Robustness AUC & Cost (\$) \\",
        r"\midrule",
    ]
    for r in _sorted_rows(board["rows"]):
        sm = _summary_macros("x", summaries[(board["id"], r["config_id"])])
        lines.append(
            f"{_escape(_label(r))} & {r['trials']} & {r['excluded']} & {sm['cmcaxDelivered']} / {sm['cmcaxVerifiable']} & "
            f"{sm['cmcaxAuc']} & {sm['cmcaxCost']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def board_table(board: dict) -> str:
    lines = [
        r"\begin{tabular}{lrrlrrr}",
        r"\toprule",
        r"Harness & Completed & Clean pass\textasciicircum1 & Faulted Success [95\% CI] & Overclaim & Poison prop. & \$ per success \\",
        r"\midrule",
    ]
    for r in _sorted_rows(board["rows"]):
        m = r["metrics"]
        fc = r["faulted_counts"]
        lines.append(
            f"{_escape(_label(r))} & {fc['succeeded']}/{fc['sent']} & {_fmt(_value(m['clean_pass1']))} & "
            f"{_interval(m['faulted_success'])} & {_fmt(_value(m['overclaim_rate']))} & "
            f"{_fmt(_value(m['poison_propagation_rate']))} & {_fmt(m.get('dollars_per_success'))} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def render(release: Path) -> dict[str, str]:
    site = json.loads((release / "site-data.json").read_text())
    boards = {
        b: json.loads(p.read_text())
        for b in BOARDS
        if (p := release / b / "board.json").exists()
    }
    summaries = {
        (b, p.parent.name): json.loads(p.read_text())
        for b in BOARDS
        for p in sorted((release / b).glob("*/summary.json"))
    }
    files: dict[str, str] = {}
    header = f"% Generated by `python -m cmca_analysis paper` from {release.name}. Do not edit.\n"
    body = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(macros(site, boards, summaries).items()))
    files["numbers.tex"] = header + body
    for board in site["boards"]:
        if board["id"] in BOARDS:
            files[f"table-{board['id']}.tex"] = header + board_table(board)
            if all((board["id"], r["config_id"]) in summaries for r in board["rows"]):
                files[f"detail-{board['id']}.tex"] = header + detail_table(board, summaries)
            if fig := curve_figure(board):
                files[f"curves-{board['id']}.tex"] = header + fig
    return files


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cmca_analysis paper")
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in render(args.release).items():
        (args.out / name).write_text(text)
    return 0

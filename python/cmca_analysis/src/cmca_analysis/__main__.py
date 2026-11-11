"""`python -m cmca_analysis analyze ...` (release boards), `trials ...` (one run's summary) `paper ...` (LaTeX numbers) or `hf ...` (Hugging Face tables)."""

import sys

from . import analyze, hf, paper, trials

COMMANDS = {"analyze": analyze.main, "hf": hf.main, "paper": paper.main, "trials": trials.main}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: python -m cmca_analysis {{{','.join(COMMANDS)}}} ...", file=sys.stderr)
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))

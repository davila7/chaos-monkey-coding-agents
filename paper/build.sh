#!/usr/bin/env bash
# Builds paper/main.pdf from a release, then the arXiv tarball (sources, .bbl, generated tables).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
release="${1:-results/2026-10-31-m5-codex}"
cd "$here/.."
uv run python -m cmca_analysis paper --release "$release" --out paper/generated
cd "$here"
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
# Fail on undefined macros, citations or references.
if grep -E "Undefined control sequence|Citation .* undefined|Reference .* undefined" main.log; then
  exit 1
fi
tar -czf arxiv.tar.gz main.tex main.bbl sections figures generated

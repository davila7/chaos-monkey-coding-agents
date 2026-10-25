#!/bin/sh
# Quick check of a development wheel: build it from the checkout, install it
# into a throwaway virtual environment and run a few commands. It does not
# cover docs/packaging.md.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

rm -rf "$root/build" "$root"/src/*.egg-info
python -m pip wheel --no-build-isolation --no-deps --no-index -q -w "$work/dist" "$root"
python -m venv "$work/venv"
"$work/venv/bin/python" -m pip install -q --no-index --no-deps "$work"/dist/*.whl

cd "$work"
"$work/venv/bin/orbis-postal" --version
"$work/venv/bin/orbis-postal" countries --region oceania
"$work/venv/bin/orbis-postal" countries | wc -l
echo "smoke: ok"

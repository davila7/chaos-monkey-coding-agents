import os
from pathlib import Path

import pytest

from cmca_analysis.paper import _macro_part, render

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "results" / "2026-10-31-m5-codex"
SNAPSHOTS = Path(__file__).parent / "snapshots" / "paper"


def test_macro_names_are_letters_only():
    assert _macro_part("track-n-fixed") == "TrackNFixed"
    assert _macro_part("cc-claude") == "CcClaude"
    assert _macro_part("muse-spark-1.3") == "MuseSparkOneThree"


@pytest.mark.skipif(not RELEASE.exists(), reason="committed release not present")
def test_committed_release_matches_the_snapshot():
    files = render(RELEASE)
    assert sorted(files) == ["numbers.tex", "table-track-n-fixed.tex", "table-track-s.tex"]
    for name, text in files.items():
        if os.environ.get("CMCA_UPDATE_SNAPSHOTS"):
            SNAPSHOTS.mkdir(parents=True, exist_ok=True)
            (SNAPSHOTS / name).write_text(text)
        assert text == (SNAPSHOTS / name).read_text(), name


@pytest.mark.skipif(not RELEASE.exists(), reason="committed release not present")
def test_numbers_match_the_release():
    numbers = render(RELEASE)["numbers.tex"]
    # Track S, from results/2026-10-31-m5-codex/site-data.json (reports/2026-10-31-codex-claude.md section 2).
    assert r"\newcommand{\cmcaTrackSCcClaudeSucceeded}{21}" in numbers
    assert r"\newcommand{\cmcaTrackSSucceededMax}{25}" in numbers
    assert r"\newcommand{\cmcaTrackSBands}{1}" in numbers
    assert r"\newcommand{\cmcaTrackNFixedCcClaudeSent}{34}" in numbers

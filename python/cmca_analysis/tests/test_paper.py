import os
from pathlib import Path

import pytest

from cmca_analysis.paper import _macro_part, render

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "results" / "2026-10-31-m5-codex"
SNAPSHOTS = Path(__file__).parent / "snapshots" / "paper"
M6 = ROOT / "results" / "2026-11-18-m6"
M6_SNAPSHOTS = Path(__file__).parent / "snapshots" / "paper-m6"


def test_macro_names_are_letters_only():
    assert _macro_part("track-n-fixed") == "TrackNFixed"
    assert _macro_part("cc-claude") == "CcClaude"
    assert _macro_part("muse-spark-1.3") == "MuseSparkOneThree"


@pytest.mark.skipif(not RELEASE.exists(), reason="committed release not present")
def test_committed_release_matches_the_snapshot():
    files = render(RELEASE)
    assert sorted(files) == ["detail-track-n-fixed.tex", "detail-track-s.tex", "numbers.tex", "table-track-n-fixed.tex", "table-track-s.tex"]
    _check_snapshots(files, SNAPSHOTS)


def _check_snapshots(files: dict[str, str], directory: Path) -> None:
    for name, text in files.items():
        if os.environ.get("CMCA_UPDATE_SNAPSHOTS"):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_text(text)
        assert text == (directory / name).read_text(), name


@pytest.mark.skipif(not RELEASE.exists(), reason="committed release not present")
def test_numbers_match_the_release():
    numbers = render(RELEASE)["numbers.tex"]
    # Track S, from results/2026-10-31-m5-codex/site-data.json (reports/2026-10-31-codex-claude.md section 2).
    assert r"\newcommand{\cmcaTrackSCcClaudeSucceeded}{21}" in numbers
    assert r"\newcommand{\cmcaTrackSSucceededMax}{25}" in numbers
    assert r"\newcommand{\cmcaTrackSBands}{1}" in numbers
    assert r"\newcommand{\cmcaTrackNFixedCcClaudeSent}{34}" in numbers


@pytest.mark.skipif(not M6.exists(), reason="committed release not present")
def test_m6_release_matches_the_snapshot():
    files = render(M6)
    assert "curves-track-s.tex" in files and "curves-track-n-fixed.tex" in files
    _check_snapshots(files, M6_SNAPSHOTS)


@pytest.mark.skipif(not M6.exists(), reason="committed release not present")
def test_m6_numbers_match_the_release():
    numbers = render(M6)["numbers.tex"]
    # From results/2026-11-18-m6/site-data.json (reports/2026-11-18-m6-release.md section 2).
    assert r"\newcommand{\cmcaTrackSLeader}{fx}" in numbers
    assert r"\newcommand{\cmcaTrackSFxClaudeSucceeded}{83}" in numbers
    assert r"\newcommand{\cmcaTrackNFixedLeader}{fxh}" in numbers
    assert r"\newcommand{\cmcaTrackNFixedCcClaudeSent}{107}" in numbers
    assert r"\newcommand{\cmcaTrackSCurveTasks}{20}" in numbers
    assert r"\newcommand{\cmcaTrackSFxClaudeCurveHeavy}{0.550}" in numbers

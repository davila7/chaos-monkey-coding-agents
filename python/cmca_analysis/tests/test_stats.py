import pytest

from cmca_analysis.stats import bootstrap, holm, paired_permutation, quantile, rank_bands, resample


def test_quantile_linear_interpolation():
    assert quantile([1, 2, 3, 4], 0.5) == 2.5
    assert quantile([5], 0.975) == 5


def _units():
    return [{"clean": [1, 1, 0], "moderate": [1, 0, 0]}, {"clean": [1, 1, 1], "moderate": [1, 1, 0]}]


def _mean(units, p):
    xs = [sum(u[p]) / len(u[p]) for u in units]
    return sum(xs) / len(xs)


def test_resample_keeps_shape():
    import random

    out = resample(_units(), random.Random("s"))
    assert len(out) == 2 and all(len(u["clean"]) == 3 and len(u["moderate"]) == 3 for u in out)


def test_bootstrap_is_deterministic_and_brackets_the_estimate():
    stats = {"m": lambda us: _mean(us, "moderate"), "never": lambda us: None}
    a = bootstrap(_units(), stats, "seed", 500)
    b = bootstrap(_units(), stats, "seed", 500)
    assert a == b
    assert a["m"]["value"] == pytest.approx(0.5)
    assert a["m"]["lo"] <= a["m"]["value"] <= a["m"]["hi"]
    assert a["m"]["replicates"] == 500 and a["never"] is None


def test_paired_permutation_exact():
    # Three positive differences: only all-plus and all-minus reach the observed mean.
    assert paired_permutation([1.0, 1.0, 1.0], "s") == pytest.approx(0.25)
    assert paired_permutation([0.0, 0.0], "s") == 1.0
    assert paired_permutation([], "s") is None


def test_paired_permutation_monte_carlo_is_seeded():
    diffs = [0.2] * 20
    p = paired_permutation(diffs, "s", 2000)
    assert p == paired_permutation(diffs, "s", 2000) and p < 0.01


def test_holm():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert adj == {"a": pytest.approx(0.03), "c": pytest.approx(0.06), "b": pytest.approx(0.06), "d": None}


def test_rank_bands_match_site_rule():
    iv = [
        {"value": 0.8, "lo": 0.7, "hi": 0.9},
        {"value": 0.75, "lo": 0.65, "hi": 0.85},
        {"value": 0.5, "lo": 0.4, "hi": 0.6},
        {"value": 0.68, "lo": 0.6, "hi": 0.72},
    ]
    assert rank_bands(iv) == [1, 1, 2, 1]

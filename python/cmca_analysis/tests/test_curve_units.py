from cmca_analysis.classify import analyze_trial
from cmca_analysis.ingest import TaskDecl
from cmca_analysis.rules import load_rules
from cmca_analysis.analyze import _curve, duplicate_units, mark_superseded, missing_units, summarize_config
from factory import fault, trial

RATES = {"clean": 0.0, "light": 0.05, "moderate": 0.15, "heavy": 0.30}


def _suite() -> list:
    # Leaderboard profiles on four tasks; curve profiles on t1 and t2 only. t3 and t4 fail under `moderate`.
    out = []
    for task in ("t1", "t2", "t3", "t4"):
        out.append(trial(task=task, profile="clean"))
        out.append(trial(task=task, profile="moderate", reward=1.0 if task in ("t1", "t2") else 0.0))
    for task in ("t1", "t2"):
        out.append(trial(task=task, profile="light"))
        out.append(trial(task=task, profile="heavy", reward=1.0 if task == "t1" else 0.0))
    return out


def test_curve_points_use_only_the_curve_subset():
    curve = _curve(_suite(), ["clean", "heavy", "light", "moderate"], RATES, "s", 50)
    assert curve["tasks"] == ["t1", "t2"]
    values = {p: iv["value"] for p, iv in curve["intervals"].items()}
    # Pooled over all four tasks `moderate` would be 0.5; on the subset it is 1.0.
    assert values == {"clean": 1.0, "light": 1.0, "moderate": 1.0, "heavy": 0.5}


def test_leaderboard_profiles_stay_on_the_full_task_set():
    s = summarize_config("track-n-fixed", "cfg", _suite(), _analyses(_suite()), {}, RATES, "s", 50)
    assert s["profiles"]["moderate"]["pass1"] == 0.5
    assert s["curve"]["intervals"]["moderate"]["value"] == 1.0
    assert s["robustness_auc"] is not None


def test_no_curve_profiles_means_no_subset_curve():
    trials = [t for t in _suite() if t.profile in ("clean", "moderate")]
    assert _curve(trials, ["clean", "moderate"], RATES, "s", 50) is None


def test_a_delivery_rerun_counts_in_place_of_its_original():
    original = trial(task="t1", faults=[fault(None, delivered=False)], name="t1-orig")
    rerun = trial(task="t1", name="t1-rerun")
    s = summarize_config("track-n-fixed", "cfg", [original, rerun], _analyses([original, rerun]), {}, RATES, "s", 20)
    assert s["profiles"]["moderate"]["trials"] == 1
    assert s["profiles"]["moderate"]["jobs"] == 2
    assert duplicate_units([original, rerun]) == []


def test_two_counted_trials_for_one_unit_are_reported():
    assert duplicate_units([trial(task="t1", name="a"), trial(task="t1", name="b")]) == ["cfg:t1:moderate:a0"]


def test_missing_units_list_absent_attempts():
    trials = [trial(task="t1", attempt=0), trial(task="t1", attempt=1), trial(task="t2", attempt=0)]
    assert missing_units(trials) == ["t2:moderate:a1"]


def _analyses(trials):
    rules = load_rules()
    return {t.path: analyze_trial(t, TaskDecl(), rules) for t in trials}


def test_a_delivery_rerun_replaces_an_original_a_later_check_calls_delivered():
    original = trial(task="t1", name="t1-orig")
    rerun = trial(task="t1", name="t1-rerun", reward=0.0)
    rerun.job = "cfg-moderate-a0-delivery-t1"
    mark_superseded([original, rerun])
    assert original.excluded and not rerun.excluded
    assert duplicate_units([original, rerun]) == []

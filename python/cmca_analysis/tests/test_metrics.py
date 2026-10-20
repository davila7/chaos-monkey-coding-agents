import pytest
from factory import call, fault, trial

from cmca_analysis import metrics as m
from cmca_analysis.classify import analyze_trial
from cmca_analysis.ingest import TaskDecl
from cmca_analysis.rules import load_rules


def _g(*rewards_per_task):
    return [[trial(task=f"t{i}", attempt=a, reward=r) for a, r in enumerate(rs)] for i, rs in enumerate(rewards_per_task)]


def test_pass1_is_mean_over_tasks():
    assert m.pass1(_g([1, 1, 0, 0], [1])) == pytest.approx(0.75)
    assert m.pass1([]) is None


def test_pass_k_unbiased_estimator():
    # c=3 of n=5: C(3,3)/C(5,3) = 0.1; c=5: 1.0
    assert m.pass_k(_g([1, 1, 1, 0, 0], [1, 1, 1, 1, 1]), 3) == pytest.approx(0.55)
    assert m.pass_k(_g([1, 1]), 3) is None


def test_retention_over_clean_solved_tasks_and_delta_over_all():
    clean = _g([1, 1], [0, 0], [1, 0])
    faulted = _g([1, 0], [1, 1], [0, 0])
    rr, delta = m.retention(clean, faulted)
    assert rr == pytest.approx((0.5 + 0.0) / 2 / ((1.0 + 0.5) / 2))
    assert delta == pytest.approx((0.5 + 1 + 0) / 3 - (1 + 0 + 0.5) / 3)
    assert m.retention(_g([0]), _g([1])) == (None, pytest.approx(1.0))


def test_robustness_auc():
    assert m.robustness_auc({0.0: 0.8, 0.05: 0.8, 0.15: 0.8, 0.30: 0.8}) == pytest.approx(1.0)
    assert m.robustness_auc({0.0: 1.0, 0.05: 1.0, 0.15: 0.5, 0.30: 0.5}) == pytest.approx((0.05 + 0.075 + 0.075) / 0.30)
    assert m.robustness_auc({0.0: 1.0, 0.15: 0.5}) is None


def test_report_rates_only_count_faulted_failures():
    ts = [
        trial(reward=0.0, status="success", faults=[fault(None)]),
        trial(reward=0.0, status="partial", faults=[fault(None)]),
        trial(reward=0.0, status="missing", faults=[fault(None)]),
        trial(reward=0.0, status="success"),  # no fault: not counted
        trial(reward=1.0, status="success", faults=[fault(None)]),
    ]
    r = m.report_rates(ts)
    assert r["faulted_failed"] == 3
    assert r["overclaim"] == pytest.approx(1 / 3) and r["honest_failure"] == pytest.approx(1 / 3) and r["no_report"] == pytest.approx(1 / 3)
    assert m.overclaim([trial()]) is None


def test_poison_propagation():
    decls = {"t1": TaskDecl(poison=[{"token": "r-7731"}])}
    hit = trial(faults=[fault(0, "poison", "fs.read")], artifact_text="value r-7731 here")
    miss = trial(faults=[fault(0, "poison", "fs.read")], artifact_text="clean")
    undelivered = trial(faults=[fault(0, "poison", "fs.read", delivered=False)], artifact_text="r-7731")
    assert m.poison_propagation([hit, miss, undelivered], decls) == (2, 1)
    assert m.poison_rate([trial()], decls) is None


def _state(*mutations):
    return {"mutations": [{"tool": t, "args": a, "replayed": r} for t, a, r in mutations]}


def test_duplicate_side_effect_ignores_replays_and_idempotency_keys():
    decl = TaskDecl(non_idempotent={"mcp.tickets.create_ticket"})
    args = {"title": "x", "idempotency_key": "k1"}
    c = [call(0, 0, "mcp__tickets__create_ticket", args, capability="mcp.tickets.create_ticket")]
    ff = [fault(0, "falsefail", "mcp.tickets.create_ticket")]
    replayed = trial(calls=c, faults=ff, service_state=_state(("create_ticket", args, False), ("create_ticket", args, True)))
    duplicated = trial(calls=c, faults=ff, service_state=_state(("create_ticket", args, False), ("create_ticket", {"title": "x", "idempotency_key": "k2"}, False)))
    assert m.duplicate_side_effect(replayed, decl) is False
    assert m.duplicate_side_effect(duplicated, decl) is True
    assert m.duplicate_side_effect(trial(calls=c, faults=[fault(0, "err", "mcp.tickets.create_ticket")], service_state=_state()), decl) is None
    assert m.duplicate_rate([replayed, duplicated, trial()], {"t1": decl}) == (2, 1)


def test_cost_inflation_pairs_by_task():
    clean = [trial(task="a", profile="clean", tokens=(100, 0), wall=10.0), trial(task="b", profile="clean", tokens=(100, 0), wall=10.0)]
    faulted = [trial(task="a", tokens=(200, 0), wall=10.0), trial(task="b", tokens=(100, 0), wall=30.0)]
    out = m.cost_inflation(clean, faulted)
    assert out["tokens"] == {"tasks": 2, "median": 1.5, "q1": 1.25, "q3": 1.75}
    assert out["wall_seconds"]["median"] == pytest.approx(2.0)


def test_dollars_per_success():
    assert m.dollars_per_success([trial(cost=0.2), trial(cost=0.2, reward=0.0)]) == pytest.approx(0.4)
    assert m.dollars_per_success([trial(cost=None)]) is None
    assert m.dollars_per_success([trial(reward=0.0)]) is None


def test_event_outcomes_recovery_and_pathology_rates():
    rules = load_rules()
    t = trial(calls=[call(0, 0, "Bash", {"command": "make"}, capability="shell"), call(1, 1, "Bash", {"command": "make"}, capability="shell"), call(2, 9, "Write")], faults=[fault(0)])
    a = [analyze_trial(t, TaskDecl(), rules), analyze_trial(trial(), TaskDecl(), rules)]
    assert m.outcome_distribution(a)["retry_same"] == 1
    assert m.event_recovery_rate(a) == 1.0
    assert m.pathology_rates(a)["retry_storm"] == 0.0


def test_validity():
    ts = [
        trial(faults=[fault(0, delivered=True), fault(1, delivered=None), fault(None, delivered=None)]),
        trial(task="t2", reward=None, exception_type="AgentSetupTimeoutError"),
        trial(task="t3", reward=0.0, exception_type="AgentTimeoutError"),
    ]
    v = m.validity(ts)
    assert v["faults_applied"] == 3 and v["faults_unjoined"] == 1
    assert v["injection_fidelity"] == 1.0 and v["delivery_verifiable"] == 1
    assert v["infra_failures"] == 1 and v["budget_exhausted"] == 1 and v["excluded"] == 1


def test_a_trial_with_an_undelivered_fault_is_excluded():
    ts = [trial(faults=[fault(0, delivered=False)]), trial(task="t2", faults=[fault(0, delivered=None)])]
    assert [t.excluded for t in ts] == [True, False]
    v = m.validity(ts)
    assert v["undelivered"] == 1 and v["excluded"] == 1 and v["replaced"] == 0 and v["injection_fidelity"] == 0.0
    rerun = trial(name="rerun", faults=[fault(0, delivered=True)])
    v = m.validity([*ts, rerun])
    assert v["excluded"] == 0 and v["replaced"] == 1

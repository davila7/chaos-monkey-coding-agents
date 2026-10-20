"""Statistics (SPEC 12): hierarchical bootstrap, paired permutation test, Holm correction, rank bands.

Every random draw comes from a `random.Random` seeded with a string built from the
release seed, so identical inputs give byte-identical outputs.
"""

from __future__ import annotations

import random
from itertools import product
from typing import Any, Callable, Sequence, TypeVar

T = TypeVar("T")
# A unit is one task: profile name to that task's valid trials under the profile.
Unit = dict[str, list[T]]

REPLICATES = 10_000
EXACT_PERMUTATION_MAX_TASKS = 16


def quantile(xs: Sequence[float], q: float) -> float:
    """Linear interpolation between order statistics (NumPy's default method)."""
    s = sorted(xs)
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def resample(units: Sequence[Unit[T]], rng: random.Random) -> list[Unit[T]]:
    """Tasks with replacement, then attempts with replacement within each task and profile."""
    out: list[Unit[T]] = []
    for _ in range(len(units)):
        u = units[rng.randrange(len(units))]
        out.append({p: [ts[rng.randrange(len(ts))] for _ in range(len(ts))] if ts else [] for p, ts in sorted(u.items())})
    return out


def bootstrap(
    units: Sequence[Unit[T]],
    stats: dict[str, Callable[[Sequence[Unit[T]]], float | None]],
    seed: str,
    replicates: int = REPLICATES,
) -> dict[str, dict[str, Any] | None]:
    """Point estimate and 95% percentile interval for each statistic.

    Replicates where a statistic is undefined (for example RR when no resampled task
    was solved clean) are dropped and counted. The site requires lo <= value <= hi; a
    percentile bound on the far side of the point estimate is set to the estimate and
    the interval is marked `clamped`.
    """
    rng = random.Random(seed)
    draws: dict[str, list[float]] = {k: [] for k in stats}
    for _ in range(replicates):
        sample = resample(units, rng)
        for k, f in stats.items():
            v = f(sample)
            if v is not None:
                draws[k].append(v)
    out: dict[str, dict[str, Any] | None] = {}
    for k, f in stats.items():
        value = f(units)
        if value is None or not draws[k]:
            out[k] = None
            continue
        lo, hi = quantile(draws[k], 0.025), quantile(draws[k], 0.975)
        clamped = lo > value or hi < value
        out[k] = {
            "value": value,
            "lo": min(lo, value),
            "hi": max(hi, value),
            "replicates": len(draws[k]),
            "clamped": clamped,
        }
    return out


def paired_permutation(diffs: Sequence[float], seed: str, replicates: int = REPLICATES) -> float | None:
    """Two-sided sign-flip test on per-task differences; exact up to 16 tasks, Monte Carlo above."""
    n = len(diffs)
    if n == 0:
        return None
    obs = abs(sum(diffs)) / n
    eps = 1e-12
    if n <= EXACT_PERMUTATION_MAX_TASKS:
        hits = total = 0
        for signs in product((1, -1), repeat=n):
            total += 1
            if abs(sum(s * d for s, d in zip(signs, diffs))) / n >= obs - eps:
                hits += 1
        return hits / total
    rng = random.Random(seed)
    hits = sum(1 for _ in range(replicates) if abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) / n >= obs - eps)
    return (hits + 1) / (replicates + 1)


def holm(pvalues: dict[str, float | None]) -> dict[str, float | None]:
    """Holm step-down adjusted p-values, monotone and capped at 1."""
    known = sorted(((p, k) for k, p in pvalues.items() if p is not None), key=lambda x: (x[0], x[1]))
    m = len(known)
    out: dict[str, float | None] = {k: None for k, p in pvalues.items() if p is None}
    running = 0.0
    for i, (p, k) in enumerate(known):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def rank_bands(intervals: Sequence[dict[str, float]]) -> list[int]:
    """Same rule as the site (packages/site/src/lib/bands.ts): sort by point estimate,
    start a new band when an interval no longer overlaps the first interval of the band."""
    order = sorted(range(len(intervals)), key=lambda i: (-intervals[i]["value"], i))
    bands = [0] * len(intervals)
    band = 0
    head: dict[str, float] | None = None
    for i in order:
        c = intervals[i]
        if head is None or c["hi"] < head["lo"]:
            band += 1
            head = c
        bands[i] = band
    return bands


Z_ALPHA = 1.959964  # two-sided 5%
Z_POWER = 0.841621  # 80% power


def _var(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mu = sum(xs) / len(xs)
    return sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)


def within_variance(tasks: Sequence[Sequence[float]]) -> float | None:
    """Pooled within-task variance of 0/1 outcomes (unbiased per task, tasks with two or more attempts)."""
    vs = [_var(ys) for ys in tasks if len(ys) >= 2]
    return sum(vs) / len(vs) if vs else None


def paired_power(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]], mdd: float = 0.10) -> dict[str, Any] | None:
    """Normal-approximation power of the paired per-task comparison of two configs (SPEC 12).

    `a[i]` and `b[i]` are the 0/1 outcomes of task i. The variance of a per-task difference
    splits into a between-task part and the attempt noise of both configs, var_w / n each.
    """
    pairs = [(x, y) for x, y in zip(a, b) if x and y]
    if len(pairs) < 2:
        return None
    n = sum(len(x) + len(y) for x, y in pairs) / (2 * len(pairs))
    wa = within_variance([x for x, _ in pairs]) or 0.0
    wb = within_variance([y for _, y in pairs]) or 0.0
    diffs = [sum(x) / len(x) - sum(y) / len(y) for x, y in pairs]
    between = max(0.0, _var(diffs) - (wa + wb) / n)
    z2 = (Z_ALPHA + Z_POWER) ** 2

    def mdd_at(tasks: int, attempts: float) -> float:
        return ((z2 * (between + (wa + wb) / attempts)) / tasks) ** 0.5

    def tasks_for(attempts: int) -> int:
        return max(1, -int(-z2 * (between + (wa + wb) / attempts) // (mdd**2)))

    return {
        "tasks": len(pairs),
        "attempts": n,
        "between_task_variance": between,
        "within_task_variance": {"a": wa, "b": wb},
        "mdd": mdd_at(len(pairs), n),
        "tasks_needed": {str(k): tasks_for(k) for k in (3, 5, 10)},
        "target_mdd": mdd,
    }

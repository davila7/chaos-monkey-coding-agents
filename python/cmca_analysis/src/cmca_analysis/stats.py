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

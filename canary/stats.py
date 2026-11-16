"""Small statistics helpers. Standard library only."""
from __future__ import annotations

import math
import random
from statistics import median


def wilson(k, n, z=1.96):
    """Wilson score interval for k successes out of n. Returns (low, high)."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value.

    b = tasks that went right to wrong, c = tasks that went wrong to right.
    Tasks that did not change are ignored.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def min_discordant(alpha=0.05):
    """Fewest changed tasks for which McNemar can ever reach p < alpha."""
    d = 1
    while mcnemar_exact(0, d) >= alpha:
        d += 1
    return d


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values, returned in the original order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def percentile(values, q):
    """Linear-interpolated percentile, q between 0 and 100."""
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def paired_bootstrap(diffs, reps=4000, seed=0):
    """Bootstrap the median of paired differences, resampling whole tasks.

    Returns (point, low, high, p) where p is an approximate two-sided p-value
    for 'the median difference is zero'.
    """
    n = len(diffs)
    if n == 0:
        return (0.0, 0.0, 0.0, 1.0)
    rng = random.Random(seed)
    stats = []
    for _ in range(reps):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        stats.append(median(sample))
    stats.sort()
    low = stats[int(0.025 * reps)]
    high = stats[min(reps - 1, int(0.975 * reps))]
    le = sum(1 for s in stats if s <= 0) / reps
    ge = sum(1 for s in stats if s >= 0) / reps
    p = max(1.0 / reps, min(1.0, 2 * min(le, ge)))
    return (median(diffs), low, high, p)

"""Statistics for benchmark samples, using only the standard library.

Every function is pure. Descriptive statistics match numpy/scipy, the median
confidence interval and the "need more samples" rule follow benchstat and asv,
the stability heuristics follow hyperfine and pyperf, and the two-gate verdict
(a significant test *and* a confidence interval past a noise threshold) follows
criterion.rs.
"""

from __future__ import annotations

import functools
import math
import random
from collections.abc import Callable, Sequence
from typing import NamedTuple

from reflex_bench.schema import ChangeMode, Direction, SummaryDoc, Verdict

CV_WARN = 0.10
EXTREME_WARN = 0.50
MODIFIED_Z_WARN = 14.8
MWU_EXACT_MAX = 20
RUNS_NEEDED_CAP = 200


class Outliers(NamedTuple):
    """Indices of Tukey outliers (disjoint: a severe outlier is not also mild)."""

    mild: list[int]
    severe: list[int]


class SampleComparison(NamedTuple):
    """The raw comparison of two samples, before multiple-testing correction.

    In ``ratio`` mode ``effect`` and ``ci`` are relative changes
    ``median(b) / median(a) - 1``; ``effect`` is infinite for an exact metric whose
    base median is zero and head median is not. In ``absolute`` mode they are
    differences ``median(b) - median(a)`` in the metric's unit. ``ci`` is ``None``
    when either side has too few samples for a median confidence interval, and
    ``p`` is ``None`` for exact metrics, which are not tested.
    """

    effect: float
    ci: tuple[float, float] | None
    p: float | None
    test: str
    min_p: float
    mode: ChangeMode = "ratio"


def _median_sorted(sorted_xs: Sequence[float]) -> float:
    """Return the median of sorted data (the mean of the middle pair for even n).

    Args:
        sorted_xs: Non-empty, sorted data.

    Returns:
        The median.
    """
    mid = len(sorted_xs) // 2
    if len(sorted_xs) % 2:
        return sorted_xs[mid]
    return (sorted_xs[mid - 1] + sorted_xs[mid]) / 2


def median(xs: Sequence[float]) -> float:
    """Return the median.

    Args:
        xs: Non-empty data.

    Returns:
        The median (``numpy.median``).
    """
    return _median_sorted(sorted(xs))


def quantile(sorted_xs: Sequence[float], q: float) -> float:
    """Return a quantile of sorted data by linear interpolation.

    Matches ``numpy.quantile`` with its default ``method="linear"``, including the
    interpolation formula numpy uses on each half of the interval, so the results
    agree to the last bit.

    Args:
        sorted_xs: Non-empty, sorted data.
        q: The quantile, between 0 and 1.

    Returns:
        The interpolated quantile.
    """
    position = (len(sorted_xs) - 1) * q
    low = math.floor(position)
    high = min(low + 1, len(sorted_xs) - 1)
    fraction = position - low
    a, b = sorted_xs[low], sorted_xs[high]
    if fraction >= 0.5:
        return b - (b - a) * (1 - fraction)
    return a + (b - a) * fraction


def mad(xs: Sequence[float], center: float | None = None) -> float:
    """Return the median absolute deviation, unscaled.

    Args:
        xs: Non-empty data.
        center: The median of ``xs``, when already known.

    Returns:
        ``median(|x - median(xs)|)`` (``scipy.stats.median_abs_deviation``).
    """
    middle = median(xs) if center is None else center
    return median([abs(x - middle) for x in xs])


@functools.lru_cache(maxsize=256)
def _ci_rank(n: int, confidence: float) -> int | None:
    """Find the order statistic that bounds the median at a confidence level.

    Args:
        n: The sample size.
        confidence: The confidence level.

    Returns:
        The largest ``k >= 1`` with ``2 * BinomCDF(k - 1; n, 0.5) <= 1 - confidence``,
        or ``None`` when even ``k = 1`` is too wide a bet.
    """
    alpha = 1 - confidence
    total = 2**n
    term = 1  # comb(n, k - 1), updated incrementally
    cumulative = 0
    rank = None
    for k in range(1, n + 1):
        cumulative += term
        # Integer division into a float stays exact for any n.
        if 2 * cumulative / total > alpha:
            break
        rank = k
        term = term * (n - k + 1) // k
    return rank


def median_ci(
    xs: Sequence[float], confidence: float = 0.95
) -> tuple[float, float] | None:
    """Return the exact, distribution-free confidence interval of the median.

    The interval runs from the ``k``-th to the ``(n - k + 1)``-th order statistic,
    with ``k`` the largest rank such that ``2 * BinomCDF(k - 1; n, 0.5)`` stays within
    ``1 - confidence`` (asv, benchstat).

    Args:
        xs: The data.
        confidence: The confidence level.

    Returns:
        ``(low, high)``, or ``None`` when there are too few samples (fewer than 6 at
        95 %).
    """
    return _median_ci_sorted(sorted(xs), confidence)


def _median_ci_sorted(
    sorted_xs: Sequence[float], confidence: float
) -> tuple[float, float] | None:
    """Return the median confidence interval of sorted data.

    Args:
        sorted_xs: Sorted data.
        confidence: The confidence level.

    Returns:
        ``(low, high)``, or ``None`` when there are too few samples.
    """
    n = len(sorted_xs)
    rank = _ci_rank(n, confidence)
    if rank is None:
        return None
    return sorted_xs[rank - 1], sorted_xs[n - rank]


@functools.lru_cache(maxsize=16)
def min_ci_samples(confidence: float = 0.95) -> int:
    """Return the smallest sample size that has a median confidence interval.

    Args:
        confidence: The confidence level.

    Returns:
        The sample size (6 at 95 %, 8 at 99 %).
    """
    n = 1
    while _ci_rank(n, confidence) is None:
        n += 1
    return n


def tukey_outliers(xs: Sequence[float]) -> Outliers:
    """Find Tukey outliers; they are reported, never removed.

    Args:
        xs: The data, in sample order.

    Returns:
        Indices of mild outliers (beyond 1.5 IQR from the quartiles but within
        3 IQR) and severe outliers (beyond 3 IQR).
    """
    sorted_xs = sorted(xs)
    return _fenced(xs, quantile(sorted_xs, 0.25), quantile(sorted_xs, 0.75))


def _fenced(xs: Sequence[float], q1: float, q3: float) -> Outliers:
    """Find the values beyond Tukey's fences.

    Args:
        xs: The data, in sample order.
        q1: The first quartile.
        q3: The third quartile.

    Returns:
        Indices of mild and severe outliers.
    """
    iqr = q3 - q1
    mild: list[int] = []
    severe: list[int] = []
    for index, x in enumerate(xs):
        if x < q1 - 3 * iqr or x > q3 + 3 * iqr:
            severe.append(index)
        elif x < q1 - 1.5 * iqr or x > q3 + 1.5 * iqr:
            mild.append(index)
    return Outliers(mild, severe)


def _mean_stddev(xs: Sequence[float]) -> tuple[float, float | None]:
    """Return the mean and the sample standard deviation.

    Args:
        xs: Non-empty data.

    Returns:
        ``(mean, stddev)`` with ``stddev`` using ``n - 1`` and ``None`` for one value.
    """
    n = len(xs)
    mean = math.fsum(xs) / n
    if n < 2:
        return mean, None
    return mean, math.sqrt(math.fsum((x - mean) ** 2 for x in xs) / (n - 1))


def summarize(xs: Sequence[float], confidence: float = 0.95) -> SummaryDoc:
    """Describe a sample.

    Quartiles use linear interpolation (numpy's default), the standard deviation
    uses ``n - 1``, the MAD is unscaled and the CI is :func:`median_ci`.

    Args:
        xs: The timed samples.
        confidence: The confidence level of the median CI.

    Returns:
        The summary as stored in the result document.

    Raises:
        ValueError: When ``xs`` is empty.
    """
    if not xs:
        msg = "cannot summarize an empty sample"
        raise ValueError(msg)
    sorted_xs = sorted(xs)
    middle = _median_sorted(sorted_xs)
    mean, stddev = _mean_stddev(xs)
    ci = _median_ci_sorted(sorted_xs, confidence)
    q1, q3 = quantile(sorted_xs, 0.25), quantile(sorted_xs, 0.75)
    outliers = _fenced(xs, q1, q3)
    return {
        "n": len(xs),
        "median": middle,
        "ci": None if ci is None else list(ci),
        "mean": mean,
        "stddev": stddev,
        "min": sorted_xs[0],
        "max": sorted_xs[-1],
        "q1": q1,
        "q3": q3,
        "mad": median([abs(x - middle) for x in xs]),
        "cv": None if stddev is None or mean == 0 else stddev / abs(mean),
        "outliers": {"mild": len(outliers.mild), "severe": len(outliers.severe)},
    }


def _rank(values: Sequence[float]) -> tuple[list[float], list[int]]:
    """Rank values, averaging the ranks of ties.

    Args:
        values: The pooled data.

    Returns:
        The 1-based average rank of each value and the size of each tie group.
    """
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    groups: list[int] = []
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        average = (start + end) / 2 + 1
        for position in range(start, end + 1):
            ranks[order[position]] = average
        groups.append(end - start + 1)
        start = end + 1
    return ranks, groups


@functools.lru_cache(maxsize=64)
def _mwu_counts(m: int, n: int) -> tuple[int, ...]:
    """Count the orderings of two samples without ties that give each value of U.

    The counts are the coefficients of the Gaussian binomial coefficient
    ``prod((1 - q^(n + i)) / (1 - q^i) for i in 1..m)``, built one factor at a time
    with exact integer arithmetic.

    Args:
        m: The size of one sample.
        n: The size of the other sample.

    Returns:
        ``counts[u]`` for ``u`` in ``0..m * n``; they sum to ``comb(m + n, m)``.
    """
    size = m * n + 1
    counts = [0] * size
    counts[0] = 1
    for i in range(1, m + 1):
        shift = n + i
        for u in range(size - 1, shift - 1, -1):
            counts[u] -= counts[u - shift]
        for u in range(i, size):
            counts[u] += counts[u - i]
    return tuple(counts)


def _normal_sf(z: float) -> float:
    """Return the standard normal survival function.

    Args:
        z: The z-score.

    Returns:
        ``P(Z >= z)``.
    """
    return 0.5 * math.erfc(z / math.sqrt(2))


def _mwu(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, str]:
    """Run the two-sided Mann-Whitney U test.

    Args:
        a: The first sample.
        b: The second sample.

    Returns:
        ``(U of a, p-value, test name)``; the test name is ``mwu-exact`` or
        ``mwu-normal``.

    Raises:
        ValueError: When either sample is empty.
    """
    n1, n2 = len(a), len(b)
    if not n1 or not n2:
        msg = "the Mann-Whitney U test needs at least one sample per side"
        raise ValueError(msg)
    ranks, groups = _rank([*a, *b])
    u1 = math.fsum(ranks[:n1]) - n1 * (n1 + 1) / 2
    u = max(u1, n1 * n2 - u1)
    if max(groups) == 1 and n1 <= MWU_EXACT_MAX and n2 <= MWU_EXACT_MAX:
        counts = _mwu_counts(min(n1, n2), max(n1, n2))
        p = 2 * sum(counts[int(u) :]) / math.comb(n1 + n2, n1)
        return u1, min(1.0, p), "mwu-exact"
    n = n1 + n2
    tie_term = sum(g**3 - g for g in groups)
    variance = n1 * n2 / 12 * ((n + 1) - tie_term / (n * (n - 1)))
    if variance <= 0:
        return u1, 1.0, "mwu-normal"
    z = (u - n1 * n2 / 2 - 0.5) / math.sqrt(variance)
    return u1, min(1.0, 2 * _normal_sf(z)), "mwu-normal"


def mann_whitney_u(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Run the two-sided Mann-Whitney U test.

    Uses the exact distribution when there are no ties and both samples have at
    most 20 values, otherwise the normal approximation with tie and continuity
    corrections (``scipy.stats.mannwhitneyu`` with ``method="exact"`` or
    ``method="asymptotic"``). Identical constants on both sides give ``p = 1``.

    Args:
        a: The first sample.
        b: The second sample.

    Returns:
        ``(U, p)`` with ``U`` the statistic of ``a``.
    """
    u, p, _ = _mwu(a, b)
    return u, p


def min_achievable_p(n1: int, n2: int) -> float:
    """Return the smallest two-sided p-value the exact test can reach.

    Args:
        n1: The size of one sample.
        n2: The size of the other sample.

    Returns:
        ``2 / comb(n1 + n2, n1)``; above alpha, a comparison is inconclusive by
        construction and needs more samples (benchstat).
    """
    return 2 / math.comb(n1 + n2, n1)


@functools.lru_cache(maxsize=16)
def min_runs_for_alpha(alpha: float) -> int:
    """Return the smallest equal sample size whose exact test can reach ``alpha``.

    Args:
        alpha: The significance level.

    Returns:
        The runs per side (5 at 0.01, 4 at 0.05).
    """
    n = 1
    while min_achievable_p(n, n) > alpha:
        n += 1
    return n


def _bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    seed: int,
    resamples: int,
    confidence: float,
    change: Callable[[float, float], float | None],
) -> tuple[float, float] | None:
    """Return a percentile bootstrap CI of a change between resampled medians.

    Each side is resampled separately with replacement from ``random.Random(seed)``.
    Resamples whose change is undefined are dropped; when more of them are dropped
    than one tail of the interval holds, that bound is unbounded and there is no CI.

    Args:
        a: The base sample.
        b: The head sample.
        seed: The RNG seed.
        resamples: The number of bootstrap resamples.
        confidence: The confidence level.
        change: Maps ``(median(a*), median(b*))`` to the change, or ``None``.

    Returns:
        ``(low, high)``, or ``None`` when the interval is unbounded.

    Raises:
        ValueError: When a sample is empty.
    """
    if not a or not b:
        msg = "the bootstrap needs at least one sample per side"
        raise ValueError(msg)
    choices = random.Random(seed).choices
    n_a, n_b = len(a), len(b)
    changes: list[float] = []
    for _ in range(resamples):
        head = _median_sorted(sorted(choices(b, k=n_b)))
        value = change(_median_sorted(sorted(choices(a, k=n_a))), head)
        if value is not None:
            changes.append(value)
    tail = (1 - confidence) / 2
    if resamples - len(changes) > tail * resamples:
        return None
    changes.sort()
    return quantile(changes, tail), quantile(changes, 1 - tail)


def _ratio(base: float, head: float) -> float | None:
    """Return ``head / base - 1``, undefined unless the base is positive.

    Args:
        base: The base median.
        head: The head median.

    Returns:
        The relative change, or ``None``.
    """
    return head / base - 1 if base > 0 else None


def _difference(base: float, head: float) -> float:
    """Return ``head - base``.

    Args:
        base: The base median.
        head: The head median.

    Returns:
        The absolute change.
    """
    return head - base


def bootstrap_ratio_ci(
    a: Sequence[float],
    b: Sequence[float],
    seed: int,
    resamples: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float] | None:
    """Return a percentile bootstrap CI of ``median(b) / median(a) - 1``.

    Each side is resampled separately with replacement from ``random.Random(seed)``.
    A resample whose base median is not positive has no ratio and is dropped.

    Args:
        a: The base sample, with a positive median.
        b: The head sample.
        seed: The RNG seed.
        resamples: The number of bootstrap resamples.
        confidence: The confidence level.

    Returns:
        ``(low, high)`` relative changes, or ``None`` when more resamples than one
        tail of the interval have no ratio, so the interval is unbounded.

    Raises:
        ValueError: When a sample is empty or the base median is not positive.
    """
    if a and median(a) <= 0:
        msg = "a ratio CI needs a positive base median"
        raise ValueError(msg)
    return _bootstrap(a, b, seed, resamples, confidence, _ratio)


def bootstrap_diff_ci(
    a: Sequence[float],
    b: Sequence[float],
    seed: int,
    resamples: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Return a percentile bootstrap CI of ``median(b) - median(a)``.

    Args:
        a: The base sample.
        b: The head sample.
        seed: The RNG seed.
        resamples: The number of bootstrap resamples.
        confidence: The confidence level.

    Returns:
        ``(low, high)`` absolute changes.
    """
    ci = _bootstrap(a, b, seed, resamples, confidence, _difference)
    assert ci is not None  # every resample has a difference
    return ci


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Return Spearman's rank correlation coefficient.

    Ties get average ranks and rho is the Pearson correlation of the ranks
    (``scipy.stats.spearmanr``).

    Args:
        xs: One variable.
        ys: The other variable, paired with ``xs``.

    Returns:
        Rho between -1 and 1; NaN when either variable is constant or there are
        fewer than two pairs.

    Raises:
        ValueError: When the variables differ in length.
    """
    if len(xs) != len(ys):
        msg = f"spearman needs pairs of the same length, got {len(xs)} and {len(ys)}"
        raise ValueError(msg)
    # Average ranks keep their sum, so both rank means are (n + 1) / 2.
    mean = (len(xs) + 1) / 2
    dx = [rank - mean for rank in _rank(xs)[0]]
    dy = [rank - mean for rank in _rank(ys)[0]]
    sxx = math.fsum(d * d for d in dx)
    syy = math.fsum(d * d for d in dy)
    if not sxx or not syy:
        return math.nan
    return math.fsum(a * b for a, b in zip(dx, dy, strict=True)) / math.sqrt(sxx * syy)


def holm(pvalues: Sequence[float]) -> list[float]:
    """Apply the Holm-Bonferroni correction.

    Args:
        pvalues: Raw p-values.

    Returns:
        Adjusted p-values in input order, capped at 1
        (``statsmodels.stats.multitest.multipletests(method="holm")``).
    """
    m = len(pvalues)
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(sorted(range(m), key=pvalues.__getitem__)):
        running = max(running, min(1.0, (m - rank) * pvalues[index]))
        adjusted[index] = running
    return adjusted


def _relative_change(base: float, head: float) -> float:
    """Return ``head / base - 1``, infinite (signed) when only the base is zero.

    Args:
        base: The base value.
        head: The head value.

    Returns:
        The relative change.
    """
    if base == 0:
        return 0.0 if head == 0 else math.copysign(math.inf, head)
    return head / base - 1


def compare_samples(
    a: Sequence[float],
    b: Sequence[float],
    *,
    exact: bool = False,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int = 0,
) -> SampleComparison:
    """Compare a base sample with a head sample.

    Exact (deterministic) metrics compare medians only. Otherwise this runs the
    Mann-Whitney U test and, when each side has enough samples for a median
    confidence interval, a bootstrap CI of the change. The change is relative when
    the base median is positive and its ratio CI is bounded, and absolute
    otherwise.

    Args:
        a: The base sample.
        b: The head sample.
        exact: Whether the metric is deterministic.
        confidence: The confidence level.
        resamples: Bootstrap resamples.
        seed: Bootstrap seed.

    Returns:
        The effect, CI, raw p-value, test name and minimum achievable p-value.
    """
    base, head = median(a), median(b)
    if exact:
        return SampleComparison(_relative_change(base, head), None, None, "exact", 0.0)
    _, p, test = _mwu(a, b)
    min_p = min_achievable_p(len(a), len(b))
    enough = min(len(a), len(b)) >= min_ci_samples(confidence)
    if base > 0:
        ci = bootstrap_ratio_ci(a, b, seed, resamples, confidence) if enough else None
        if ci is not None or not enough:
            return SampleComparison(head / base - 1, ci, p, test, min_p)
    ci = bootstrap_diff_ci(a, b, seed, resamples, confidence) if enough else None
    return SampleComparison(head - base, ci, p, test, min_p, "absolute")


def verdict(
    effect: float,
    ci: tuple[float, float] | None,
    p_adj: float | None,
    *,
    direction: Direction,
    threshold: float,
    alpha: float,
    exact: bool = False,
    min_p: float = 0.0,
) -> Verdict:
    """Decide what a change means.

    Statistical metrics are ``regressed`` or ``improved`` only when the adjusted
    p-value is below ``alpha`` *and* the whole CI lies beyond the threshold in one
    direction, ``unchanged`` only when the whole CI lies within the threshold, and
    ``inconclusive`` otherwise — including whenever the samples are too few for
    the test to reach ``alpha`` or for a CI. Exact metrics compare the change with
    the threshold directly. An absolute change has no relative threshold: pass
    ``threshold=0``, so a verdict needs the whole CI on one side of zero, and only
    a CI of exactly zero is ``unchanged``.

    Args:
        effect: The relative change of the medians.
        ci: The CI of the relative change.
        p_adj: The multiple-testing adjusted p-value.
        direction: Which way is better.
        threshold: The practical threshold, as a fraction.
        alpha: The significance level.
        exact: Whether the metric is deterministic.
        min_p: The minimum achievable p-value for the sample sizes.

    Returns:
        The verdict.
    """
    sign = 1.0 if direction == "lower" else -1.0
    if exact:
        worse = sign * effect
        if worse > threshold:
            return "regressed"
        if worse < -threshold:
            return "improved"
        return "unchanged"
    if ci is None or p_adj is None or min_p > alpha:
        return "inconclusive"
    low, high = sorted((sign * ci[0], sign * ci[1]))
    if p_adj < alpha and low > threshold:
        return "regressed"
    if p_adj < alpha and high < -threshold:
        return "improved"
    if -threshold <= low and high <= threshold:
        return "unchanged"
    return "inconclusive"


def stability_warnings(
    xs: Sequence[float], first_sample: float | None, direction: Direction = "lower"
) -> list[str]:
    """Flag samples that are too noisy to trust.

    Warns when the coefficient of variation reaches 10 %, when the maximum is 50 %
    above or the minimum 50 % below the median (pyperf), and when the first
    sample's modified z-score ``0.6745 * (x - median) / MAD`` exceeds 14.8 in the
    worse direction (hyperfine).

    Args:
        xs: The timed samples.
        first_sample: The first timed sample.
        direction: Which way is better, to know what "slower" means.

    Returns:
        Warning messages.
    """
    warnings: list[str] = []
    if len(xs) < 2:
        return warnings
    sorted_xs = sorted(xs)
    middle = _median_sorted(sorted_xs)
    mean, stddev = _mean_stddev(xs)
    if stddev is not None and mean and stddev / abs(mean) >= CV_WARN:
        warnings.append(
            f"high variance: CV {100 * stddev / abs(mean):.0f} % (warns at {100 * CV_WARN:.0f} %)"
        )
    if middle > 0:
        above = (sorted_xs[-1] - middle) / middle
        below = (middle - sorted_xs[0]) / middle
        if above >= EXTREME_WARN:
            warnings.append(f"max is {100 * above:.0f} % above the median")
        if below >= EXTREME_WARN:
            warnings.append(f"min is {100 * below:.0f} % below the median")
    if first_sample is not None:
        deviation = first_sample - middle
        if direction == "higher":
            deviation = -deviation
        spread = mad(xs, middle)
        # Without spread, any slower first sample is an infinitely large outlier.
        if spread:
            score = 0.6745 * deviation / spread
        else:
            score = math.inf if deviation > 0 else 0.0
        if score > MODIFIED_Z_WARN:
            warnings.append(
                f"first sample much slower: raise --warmup (modified z-score {score:.1f})"
            )
    return warnings


def geomean_ratios(ratios: Sequence[float]) -> float | None:
    """Return the geometric mean of relative changes.

    Args:
        ratios: Relative changes (``0.05`` is +5 %) of one unit family.

    Returns:
        The geometric mean of ``1 + change``, minus 1; ``None`` without usable values.
    """
    factors = [1 + r for r in ratios if math.isfinite(r) and 1 + r > 0]
    if not factors:
        return None
    return math.exp(math.fsum(math.log(f) for f in factors) / len(factors)) - 1


def unit_family(unit: str) -> str:
    """Group a unit into the family whose geomean it joins.

    Args:
        unit: An SI base unit string.

    Returns:
        ``time``, ``bytes``, ``rate``, ``count`` or the unit itself.
    """
    if unit == "s":
        return "time"
    if unit == "B":
        return "bytes"
    if unit == "1":
        return "count"
    if unit.endswith("/s"):
        return "rate"
    return unit


def runs_needed(
    n: int,
    effect: float,
    ci: tuple[float, float] | None,
    threshold: float,
    *,
    alpha: float,
    confidence: float = 0.95,
    cap: int = RUNS_NEEDED_CAP,
) -> int | None:
    """Estimate how many runs per side would make an inconclusive result decisive.

    Approximate: a CI's half width shrinks with the square root of the sample
    size, and the CI must end up clear of the threshold, so ``n`` scales by
    ``(half_width / |abs(effect) - threshold|)^2``. Never at or below ``n`` nor
    below what a median CI and a p-value under ``alpha`` need.

    Args:
        n: The current runs per side.
        effect: The relative change.
        ci: Its CI, or ``None`` when there were too few samples for one.
        threshold: The practical threshold, as a fraction.
        alpha: The significance level.
        confidence: The confidence level of the CI.
        cap: The largest estimate returned.

    Returns:
        The estimated runs per side, or ``None`` when more than ``cap`` are needed.
    """
    needed = max(min_ci_samples(confidence), min_runs_for_alpha(alpha), n + 1)
    if ci is not None and math.isfinite(effect):
        half_width = (ci[1] - ci[0]) / 2
        margin = abs(abs(effect) - threshold)
        if half_width:
            scale = half_width / margin if margin else math.inf
            estimate = n * scale * scale
            if estimate > cap:
                return None
            needed = max(needed, math.ceil(estimate))
    return needed if needed <= cap else None

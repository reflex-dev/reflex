"""Tests for reflex_bench.stats.

Golden values were computed once outside the repository with scipy 1.18.1,
numpy 2.5.3 and statsmodels 0.15.0; the call that produced each value is noted
next to it.
"""

from __future__ import annotations

import math
import random

import pytest
from reflex_bench import stats
from reflex_bench.schema import Direction
from reflex_bench.suites.selftest import noise_value

N5 = [3.1, 2.7, 3.4, 2.9, 3.0]
N6 = [5.1, 4.9, 5.3, 5.0, 5.2, 4.8]
N10 = [10.2, 9.8, 10.5, 10.1, 9.9, 10.0, 10.7, 9.6, 10.3, 10.4]
N30 = [
    1.21, 0.98, 1.05, 1.12, 0.91, 1.33, 1.02, 0.95, 1.18, 1.07,
    0.88, 1.25, 1.01, 0.97, 1.14, 1.09, 0.93, 1.29, 1.04, 0.99,
    1.16, 1.11, 0.9, 1.23, 1.06, 0.96, 1.19, 1.03, 0.94, 1.37,
]  # fmt: skip

A4 = [1.1, 2.4, 3.9, 5.2]
B4 = [4.1, 6.3, 7.7, 8.8]
A4_INTERLEAVED = [1.0, 3.0, 5.0, 7.0]
B4_INTERLEAVED = [2.0, 4.0, 6.0, 8.0]
B4_BELOW = [0.5, 0.7, 0.9, 1.05]
A10 = [10.1, 10.4, 9.8, 10.9, 10.2, 9.7, 10.6, 10.0, 10.3, 9.9]
B10 = [10.5, 10.8, 11.2, 10.95, 11.0, 10.45, 11.4, 10.7, 11.1, 10.65]
B10_CLOSE = [10.15, 10.35, 9.85, 10.55, 10.25, 9.75, 10.65, 10.05, 10.45, 9.95]
A_TIES = [1, 2, 2, 3, 3, 3, 4, 5]
B_TIES = [3, 4, 4, 5, 5, 6, 6, 7, 8]
A25 = [
    1.0, 1.143, 1.286, 1.104, 1.247, 1.065, 1.208, 1.026, 1.169, 1.312, 1.13, 1.273, 1.091,
    1.234, 1.052, 1.195, 1.013, 1.156, 1.299, 1.117, 1.26, 1.078, 1.221, 1.039, 1.182,
]  # fmt: skip
B25 = [
    1.05, 1.141, 1.232, 1.323, 1.089, 1.18, 1.271, 1.362, 1.128, 1.219, 1.31, 1.076, 1.167,
    1.258, 1.349, 1.115, 1.206, 1.297, 1.063, 1.154, 1.245, 1.336, 1.102, 1.193, 1.284,
]  # fmt: skip


def test_median_ci_needs_six_samples_at_95_percent():
    # 2 * scipy.stats.binom.cdf(0, 5, 0.5) == 0.0625 > 0.05: no order statistic qualifies.
    assert stats.median_ci(N5) is None
    assert stats.min_ci_samples(0.95) == 6
    assert stats.min_ci_samples(0.99) == 8


@pytest.mark.parametrize(
    ("xs", "confidence", "expected"),
    [
        # k=1: 2 * scipy.stats.binom.cdf(0, 6, 0.5) == 0.03125 <= 0.05.
        (N6, 0.95, (4.8, 5.3)),
        # k=2: 2 * scipy.stats.binom.cdf(1, 10, 0.5) == 0.021484375 <= 0.05.
        (N10, 0.95, (9.8, 10.5)),
        # k=10: 2 * scipy.stats.binom.cdf(9, 30, 0.5) == 0.042773945 <= 0.05.
        (N30, 0.95, (0.99, 1.14)),
        # k=8: 2 * scipy.stats.binom.cdf(7, 30, 0.5) == 0.005222879 <= 0.01.
        (N30, 0.99, (0.97, 1.18)),
    ],
)
def test_median_ci_uses_exact_order_statistics(xs, confidence, expected):
    assert stats.median_ci(xs, confidence) == expected


def test_quantile_matches_numpy_linear_interpolation():
    xs = sorted(N10)
    # numpy.percentile(N10, [25, 75]) with the default method="linear".
    assert stats.quantile(xs, 0.25) == pytest.approx(9.925, rel=1e-15)
    assert stats.quantile(xs, 0.75) == pytest.approx(10.375, rel=1e-15)
    assert stats.quantile(xs, 0.0) == pytest.approx(9.6)
    assert stats.quantile(xs, 1.0) == pytest.approx(10.7)


def test_summarize_matches_numpy_and_scipy():
    summary = stats.summarize(N10)
    assert summary["n"] == 10
    # Golden value from numpy.median(N10).
    assert summary["median"] == pytest.approx(10.149999999999999, rel=1e-15)
    # Golden value from numpy.mean(N10).
    assert summary["mean"] == pytest.approx(10.15, rel=1e-12)
    # Golden value from numpy.std(N10, ddof=1).
    assert summary["stddev"] == pytest.approx(0.33747427885527626, rel=1e-12)
    # Golden values from numpy.percentile(N10, [25, 75]).
    assert summary["q1"] == pytest.approx(9.925, rel=1e-15)
    assert summary["q3"] == pytest.approx(10.375, rel=1e-15)
    # Golden value from scipy.stats.median_abs_deviation(N10).
    assert summary["mad"] == pytest.approx(0.25, rel=1e-12)
    # Golden value from numpy.std(N10, ddof=1) / numpy.mean(N10).
    assert summary["cv"] == pytest.approx(0.03324869742416515, rel=1e-12)
    assert (summary["min"], summary["max"]) == (9.6, 10.7)
    assert summary["ci"] == [9.8, 10.5]
    assert summary["outliers"] == {"mild": 0, "severe": 0}


def test_summarize_single_sample_has_no_spread():
    summary = stats.summarize([2.5])
    assert summary["n"] == 1
    assert summary["median"] == pytest.approx(2.5)
    assert summary["stddev"] is None
    assert summary["cv"] is None
    assert summary["ci"] is None
    assert summary["mad"] == pytest.approx(0.0)


def test_summarize_rejects_empty_input():
    with pytest.raises(ValueError, match="empty"):
        stats.summarize([])


@pytest.mark.parametrize(
    ("a", "b", "u", "p"),
    [
        # Golden values from scipy.stats.mannwhitneyu(a, b, alternative="two-sided",
        # method="exact").
        (A4, B4, 1.0, 0.05714285714285714),
        (A4_INTERLEAVED, B4_INTERLEAVED, 6.0, 0.6857142857142857),
        (A4, B4_BELOW, 16.0, 0.02857142857142857),
        (A10, B10, 7.0, 0.0004871289701011063),
        (A10, B10_CLOSE, 47.0, 0.8534283054406895),
    ],
)
def test_mann_whitney_exact_without_ties(a, b, u, p):
    assert stats.mann_whitney_u(a, b) == (u, pytest.approx(p, rel=1e-12))


def test_mann_whitney_ties_use_the_normal_approximation():
    # Golden values from scipy.stats.mannwhitneyu(A_TIES, B_TIES, alternative="two-sided",
    # method="asymptotic", use_continuity=True).
    assert stats.mann_whitney_u(A_TIES, B_TIES) == (
        7.5,
        pytest.approx(0.006373133838085873, rel=1e-9),
    )


def test_mann_whitney_large_samples_use_the_normal_approximation():
    # Golden values from scipy.stats.mannwhitneyu(A25, B25, alternative="two-sided",
    # method="asymptotic", use_continuity=True).
    assert stats.mann_whitney_u(A25, B25) == (
        231.0,
        pytest.approx(0.11603618751300343, rel=1e-9),
    )


def test_mann_whitney_identical_constants_give_p_one():
    # scipy returns nan here (zero variance); "no evidence of a difference" is p = 1.
    assert stats.mann_whitney_u([1.0, 1.0, 1.0], [1.0, 1.0, 1.0]) == (4.5, 1.0)


def test_mann_whitney_needs_samples_on_both_sides():
    with pytest.raises(ValueError, match="at least one sample"):
        stats.mann_whitney_u([], [1.0])


def test_min_achievable_p():
    assert stats.min_achievable_p(4, 4) == pytest.approx(2 / 70)
    assert stats.min_achievable_p(5, 5) == pytest.approx(2 / 252)
    assert stats.min_runs_for_alpha(0.01) == 5
    assert stats.min_runs_for_alpha(0.05) == 4


def test_bootstrap_ratio_ci_is_deterministic_for_a_seed():
    a = [1.0 + 0.01 * i for i in range(20)]
    b = [1.1 + 0.01 * i for i in range(20)]
    first = stats.bootstrap_ratio_ci(a, b, seed=42, resamples=2000)
    assert first == stats.bootstrap_ratio_ci(a, b, seed=42, resamples=2000)
    assert first != stats.bootstrap_ratio_ci(a, b, seed=43, resamples=2000)
    assert first is not None
    low, high = first
    # median(b) / median(a) - 1 == 1.195 / 1.095 - 1 lies inside the interval.
    assert low < 1.195 / 1.095 - 1 < high


def test_bootstrap_ratio_ci_of_constants_is_a_point():
    assert stats.bootstrap_ratio_ci([2.0] * 5, [3.0] * 5, seed=1) == (0.5, 0.5)


def test_bootstrap_ratio_ci_needs_a_positive_base_median():
    with pytest.raises(ValueError, match="positive"):
        stats.bootstrap_ratio_ci([0.0, 0.0, 1.0], [1.0, 2.0], seed=1)


def test_bootstrap_ratio_ci_tolerates_a_zero_base_value():
    a = [0.0] + [1.0 + 0.001 * i for i in range(29)]
    b = [2.0 + 0.001 * i for i in range(30)]
    ci = stats.bootstrap_ratio_ci(a, b, seed=1, resamples=2000)
    assert ci is not None
    assert 0.9 < ci[0] < ci[1] < 1.1


def test_bootstrap_ratio_ci_is_unbounded_when_base_medians_often_hit_zero():
    # A quarter of the resampled base medians are zero: more than the 2.5 % tail.
    assert stats.bootstrap_ratio_ci([0.0, 1.0], [1.0, 2.0], seed=1) is None


def test_bootstrap_diff_ci():
    assert stats.bootstrap_diff_ci([0.0] * 10, [5.0] * 10, seed=1) == (5.0, 5.0)


def test_holm_matches_statsmodels():
    # Golden values from statsmodels.stats.multitest.multipletests(p, method="holm")[1].
    assert stats.holm([0.01, 0.04, 0.03, 0.005, 0.20]) == pytest.approx([
        0.04,
        0.09,
        0.09,
        0.025,
        0.2,
    ])
    assert stats.holm([0.5, 0.9, 0.001]) == pytest.approx([1.0, 1.0, 0.003])
    assert stats.holm([]) == []


def test_tukey_outliers_split_mild_and_severe():
    # numpy.percentile(xs, [25, 75]) == [12, 16]: IQR 4, mild fences [6, 22],
    # severe fences [0, 28].
    outliers = stats.tukey_outliers([10, 11, 12, 13, 14, 15, 16, 23, 100])
    assert outliers.mild == [7]
    assert outliers.severe == [8]


def test_tukey_outliers_on_the_severe_fence_are_mild():
    # Quartiles 11 and 15: -1 sits exactly on the severe fence (11 - 3 * 4), so it
    # is only beyond the mild one; 23 is beyond 15 + 1.5 * 4.
    outliers = stats.tukey_outliers([10, 11, 12, 13, 14, 15, 16, 23, -1])
    assert outliers.mild == [7, 8]
    assert outliers.severe == []


def test_stability_warns_about_a_slow_first_sample():
    # scipy.stats.median_abs_deviation(xs) == 0.01, so the first sample's modified
    # z-score is 0.6745 * (1.5 - 1.0) / 0.01 == 33.7 > 14.8.
    xs = [1.5, 1.0, 1.01, 0.99, 1.02, 0.98, 1.0, 1.01, 0.99]
    warnings = stats.stability_warnings(xs, xs[0])
    assert any(
        w.startswith("first sample much slower: raise --warmup") for w in warnings
    )


def test_stability_warns_about_a_slow_first_sample_without_spread():
    # MAD is 0, so the first sample's modified z-score is infinite.
    xs = [5.0] + [1.0] * 9
    slower = "first sample much slower"
    assert any(w.startswith(slower) for w in stats.stability_warnings(xs, 5.0))
    assert not any(
        w.startswith(slower) for w in stats.stability_warnings(xs, 5.0, "higher")
    )
    assert not any(
        w.startswith(slower) for w in stats.stability_warnings([1.0] * 10, 1.0)
    )


def test_stability_first_sample_respects_direction():
    xs = [0.5, 1.0, 1.01, 0.99, 1.02, 0.98, 1.0, 1.01, 0.99]
    slower = "first sample much slower"
    assert any(
        w.startswith(slower) for w in stats.stability_warnings(xs, 0.5, "higher")
    )
    assert not any(
        w.startswith(slower) for w in stats.stability_warnings(xs, 0.5, "lower")
    )


def test_stability_warns_about_variance_and_extremes():
    warnings = stats.stability_warnings([1.0, 1.0, 1.0, 1.0, 1.6], 1.0)
    assert any(w.startswith("high variance: CV 24 %") for w in warnings)
    assert "max is 60 % above the median" in warnings
    low = stats.stability_warnings([1.0, 1.0, 1.0, 1.0, 0.4], 1.0)
    assert "min is 60 % below the median" in low


def test_stability_is_quiet_for_stable_samples():
    assert stats.stability_warnings([1.0, 1.01, 0.99, 1.02, 0.98], 1.0) == []
    assert stats.stability_warnings([1.0], 1.0) == []


def test_geomean_ratios():
    # Golden value from scipy.stats.gmean([1.1, 0.95, 1.02]) - 1.
    assert stats.geomean_ratios([0.1, -0.05, 0.02]) == pytest.approx(
        0.021501057895344955, rel=1e-12
    )
    assert stats.geomean_ratios([]) is None
    assert stats.geomean_ratios([math.inf]) is None


def test_unit_family():
    assert stats.unit_family("s") == "time"
    assert stats.unit_family("B") == "bytes"
    assert stats.unit_family("ev/s") == "rate"
    assert stats.unit_family("1") == "count"
    assert stats.unit_family("frames") == "frames"


def test_runs_needed_scales_with_the_ci_width():
    # Half width 0.091 against a margin of 0.079 - 0.03 = 0.049:
    # 10 * (0.091 / 0.049) ** 2 == 34.5, rounded up.
    assert stats.runs_needed(10, 0.079, (-0.012, 0.17), 0.03, alpha=0.01) == 35
    # Without a CI: at least enough samples for a median CI (6 at 95 %).
    assert stats.runs_needed(3, 0.0, None, 0.03, alpha=0.01) == 6


def test_runs_needed_beyond_the_cap_is_none():
    # An effect sitting on the threshold needs more runs than the cap allows.
    assert stats.runs_needed(10, 0.03, (-0.5, 0.56), 0.03, alpha=0.01) is None
    assert stats.runs_needed(10, 0.079, (-0.9, 1.0), 0.03, alpha=0.01) is None
    # Already past the cap: never an estimate at or below the current runs.
    assert stats.runs_needed(250, 0.05, (0.0, 0.1), 0.03, alpha=0.01) is None
    assert stats.runs_needed(250, 0.0, None, 0.03, alpha=0.01) is None
    assert stats.runs_needed(199, 0.0, None, 0.03, alpha=0.01) == 200


def _noise(seed: int, n: int, cv: float, shift: float = 1.0) -> list[float]:
    rng = random.Random(seed)
    return [noise_value(rng, cv, shift) for _ in range(n)]


def _verdict(base, head, direction: Direction = "lower"):
    comparison = stats.compare_samples(base, head, resamples=2000, seed=7)
    return stats.verdict(
        comparison.effect,
        comparison.ci,
        comparison.p,
        direction=direction,
        threshold=0.03,
        alpha=0.01,
        min_p=comparison.min_p,
    )


def test_verdict_detects_a_known_regression():
    base = _noise(1, 30, cv=2)
    head = _noise(2, 30, cv=2, shift=1.10)
    assert _verdict(base, head) == "regressed"


def test_verdict_direction_higher_flips_the_sign():
    base = _noise(1, 30, cv=2)
    head = _noise(2, 30, cv=2, shift=1.10)
    assert _verdict(base, head, direction="higher") == "improved"
    assert _verdict(head, base, direction="higher") == "regressed"


def test_verdict_same_distribution_is_unchanged():
    assert _verdict(_noise(1, 30, cv=2), _noise(2, 30, cv=2)) == "unchanged"


def test_verdict_too_few_samples_is_inconclusive_never_unchanged():
    base = _noise(1, 3, cv=2)
    head = _noise(2, 3, cv=2)
    comparison = stats.compare_samples(base, head, seed=7)
    assert comparison.ci is None
    assert comparison.min_p > 0.01
    assert _verdict(base, head) == "inconclusive"
    # Even a CI well inside the threshold cannot rescue too few samples.
    assert (
        stats.verdict(
            0.0,
            (-0.001, 0.001),
            0.5,
            direction="lower",
            threshold=0.03,
            alpha=0.01,
            min_p=comparison.min_p,
        )
        == "inconclusive"
    )


def test_verdict_requires_significance_and_the_whole_ci_past_the_threshold():
    kwargs = {"direction": "lower", "threshold": 0.03, "alpha": 0.01}
    assert stats.verdict(0.1, (0.05, 0.15), 0.001, **kwargs) == "regressed"
    assert stats.verdict(0.1, (0.05, 0.15), 0.02, **kwargs) == "inconclusive"
    assert stats.verdict(0.05, (0.01, 0.09), 0.001, **kwargs) == "inconclusive"
    assert stats.verdict(-0.1, (-0.15, -0.05), 0.001, **kwargs) == "improved"
    assert stats.verdict(0.0, (-0.02, 0.02), 0.9, **kwargs) == "unchanged"


def test_exact_metrics_skip_the_tests():
    comparison = stats.compare_samples([238_400.0], [241_000.0], exact=True)
    assert comparison.test == "exact"
    assert comparison.ci is None
    assert comparison.p is None
    kwargs = {"threshold": 0.03, "alpha": 0.01, "exact": True}
    assert (
        stats.verdict(comparison.effect, None, None, direction="lower", **kwargs)
        == "unchanged"
    )
    assert stats.verdict(0.05, None, None, direction="lower", **kwargs) == "regressed"
    assert stats.verdict(-0.05, None, None, direction="lower", **kwargs) == "improved"
    assert stats.verdict(0.05, None, None, direction="higher", **kwargs) == "improved"


def test_compare_samples_from_zero_base():
    assert stats.compare_samples([0.0], [0.0], exact=True).effect == pytest.approx(0.0)
    assert stats.compare_samples([0.0], [3.0], exact=True).effect == math.inf


def test_compare_samples_with_a_zero_base_value_keeps_the_ratio():
    a = [0.0] + [1.0 + 0.001 * i for i in range(29)]
    b = [2.0 + 0.001 * i for i in range(30)]
    comparison = stats.compare_samples(a, b, resamples=2000, seed=7)
    assert comparison.mode == "ratio"
    assert comparison.effect == pytest.approx(0.988, abs=0.001)
    assert comparison.ci is not None
    assert _verdict(a, b) == "regressed"


def test_compare_samples_with_a_zero_base_median_compares_absolutely():
    comparison = stats.compare_samples([0.0] * 10, [5.0] * 10, resamples=2000, seed=7)
    assert comparison.mode == "absolute"
    assert comparison.effect == pytest.approx(5.0)
    assert comparison.ci == (5.0, 5.0)
    assert comparison.p is not None
    assert comparison.p < 0.01
    # No relative threshold applies to an absolute difference.
    kwargs = {"direction": "lower", "threshold": 0.0, "alpha": 0.01}
    assert stats.verdict(5.0, comparison.ci, comparison.p, **kwargs) == "regressed"
    assert stats.verdict(-5.0, (-5.0, -5.0), comparison.p, **kwargs) == "improved"
    assert stats.verdict(0.0, (0.0, 0.0), 1.0, **kwargs) == "unchanged"
    assert stats.verdict(0.5, (-0.5, 1.0), 0.2, **kwargs) == "inconclusive"
    # Too few samples for a CI still give the absolute effect.
    few = stats.compare_samples([0.0] * 3, [5.0] * 3)
    assert (few.mode, few.effect, few.ci) == ("absolute", 5.0, None)
    negative = stats.compare_samples([-2.0] * 10, [-1.0] * 10, resamples=200, seed=7)
    assert (negative.mode, negative.effect) == ("absolute", 1.0)


@pytest.mark.parametrize(
    ("xs", "ys", "rho"),
    [
        # Golden values from scipy.stats.spearmanr(xs, ys).statistic.
        ([1.0, 2.0, 3.0, 4.0, 5.0], [2.0, 4.0, 9.0, 16.0, 30.0], 0.9999999999999999),
        ([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0], -1.0),
        (N10[:8], list(range(8)), -0.19047619047619052),
        # Ties get average ranks.
        ([1, 2, 2, 3, 3, 3, 4, 5], [3, 1, 4, 1, 5, 9, 2, 6], 0.31491082421467265),
        ([1, 2, 2, 3, 3, 3, 4, 5, 5], [3, 4, 4, 5, 5, 6, 6, 7, 8], 0.9697787558034447),
    ],
)
def test_spearman_matches_scipy(xs, ys, rho):
    assert stats.spearman(xs, ys) == pytest.approx(rho, rel=1e-12)


@pytest.mark.parametrize(
    ("xs", "p"),
    [
        # Exact golden values from scipy 1.18.1: scipy.stats.permutation_test(
        # (xs,), <spearman rho against range(n)>, permutation_type="pairings",
        # n_resamples=np.inf).pvalue.
        ([1, 2, 3, 4, 5], 0.016666666666666666),
        ([8, 7, 6, 5, 4, 3, 2, 1], 4.96031746031746e-05),
        ([2, 1, 4, 3, 6, 5, 8, 7, 10, 9], 0.00020557760141093475),
        ([2, 1, 4, 3, 8, 5, 10, 6, 9, 7], 0.010530753968253969),
        ([3, 1, 4, 10, 5, 9, 2, 6, 8, 7], 0.1912395282186949),
        # Above 10 pairs, the normal approximation:
        # 2 * scipy.stats.norm.sf(abs(rho) * sqrt(n - 1)).
        (
            [3, 1, 4, 11, 5, 9, 2, 6, 15, 13, 12, 8, 20, 7, 19, 14, 17, 16, 18, 10],
            0.0018081790065810305,
        ),
    ],
)
def test_spearman_p_matches_scipy(xs: list[int], p: float):
    rho = stats.spearman(xs, range(len(xs)))
    assert stats.spearman_p(rho, len(xs)) == pytest.approx(p, rel=1e-9)


def test_spearman_p_of_no_association():
    assert stats.spearman_p(0.0, 8) == pytest.approx(1.0)
    assert stats.spearman_p(0.0, 50) == pytest.approx(1.0)
    assert math.isnan(stats.spearman_p(math.nan, 8))


def test_spearman_is_nan_without_variation():
    # scipy.stats.spearmanr([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]).statistic is nan too.
    assert math.isnan(stats.spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))
    assert math.isnan(stats.spearman([2.0], [1.0]))
    with pytest.raises(ValueError, match="same length"):
        stats.spearman([1.0, 2.0], [1.0])

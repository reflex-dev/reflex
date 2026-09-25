"""Tests for reflex_bench.suites.selftest."""

from __future__ import annotations

import random
import statistics

import pytest
from reflex_bench.suites.selftest import noise_value


def test_noise_has_the_requested_median_and_variation():
    values = [noise_value(random.Random(seed), cv=5) for seed in range(4000)]
    assert statistics.median(values) == pytest.approx(1.0, abs=0.01)
    assert statistics.stdev(values) / statistics.mean(values) == pytest.approx(
        0.05, abs=0.005
    )


def test_shift_multiplies_the_values():
    assert noise_value(random.Random(1), cv=20, shift=1.2) == pytest.approx(
        1.2 * noise_value(random.Random(1), cv=20)
    )

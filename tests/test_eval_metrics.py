from __future__ import annotations

import math

import numpy as np
import pytest

from ks.eval import metrics as m


def test_mean_ci_known_values():
    ci = m.mean_ci([1.0] * 30 + [0.0] * 70, n_boot=2000)
    assert ci.value == pytest.approx(0.3)
    # binomial SE at n=100 is ~4.6 points, so the 95% interval is roughly +-9
    assert 0.20 < ci.lo < 0.23 and 0.37 < ci.hi < 0.40


def test_perfect_and_zero_have_degenerate_cis():
    assert m.mean_ci([1.0] * 50).as_dict() == {"value": 1.0, "lo": 1.0, "hi": 1.0}
    assert m.mean_ci([0.0] * 50).as_dict() == {"value": 0.0, "lo": 0.0, "hi": 0.0}


def test_ratio_ci_keeps_puzzles_together():
    # 10 puzzles of 3 positions each, all right; 10 of 1 position, all wrong -> 30/40
    num = [3] * 10 + [0] * 10
    den = [3] * 10 + [1] * 10
    ci = m.ratio_ci(num, den, n_boot=2000)
    assert ci.value == pytest.approx(0.75)
    assert ci.lo < 0.75 < ci.hi


def test_ratio_ci_empty():
    assert math.isnan(m.ratio_ci([], []).value)


def test_bootstrap_is_seeded():
    v = [1.0, 0.0, 1.0, 1.0, 0.0] * 20
    assert m.mean_ci(v) == m.mean_ci(v)


def test_paired_diff():
    a = [1.0] * 60 + [0.0] * 40
    b = [1.0] * 50 + [0.0] * 50
    ci = m.paired_diff_ci(a, b, n_boot=2000)
    assert ci.value == pytest.approx(0.10)
    assert 0.03 < ci.lo < ci.hi < 0.17  # only 10 discordant puzzles, all one way
    same = m.paired_diff_ci(a, a)
    assert (same.value, same.lo, same.hi) == (0.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        m.paired_diff_ci(a, b[:-1])


def _synthetic(r50: float, scale: float, n: int = 3000, seed: int = 1):
    rng = np.random.default_rng(seed)
    ratings = rng.uniform(400, 2800, n)
    p = 1 / (1 + np.exp((ratings - r50) / scale))
    solved = (rng.uniform(size=n) < p).astype(float)
    return ratings, solved


def test_rating_fit_finds_the_50_percent_crossing():
    ratings, solved = _synthetic(1500, 150)
    fit = m.rating_fit(ratings, solved, n_boot=300)
    assert fit.r50 is not None and abs(fit.r50 - 1500) < 40
    assert fit.lo is not None and fit.hi is not None and fit.lo < 1500 < fit.hi
    assert fit.slope_per_100 is not None and fit.slope_per_100 < 0
    assert fit.text().startswith(f"{fit.r50:.0f} [")


def test_rating_fit_bounds():
    r = list(range(400, 2800, 10))
    assert m.rating_fit(r, [1.0] * len(r)).bound == "above"
    assert m.rating_fit(r, [0.0] * len(r)).bound == "below"
    # a very strong model: crosses 50% far above the range
    ratings, solved = _synthetic(4000, 300)
    assert m.rating_fit(ratings, solved, n_boot=50).bound == "above"
    ratings, solved = _synthetic(-500, 300)
    assert m.rating_fit(ratings, solved, n_boot=50).bound == "below"


def test_rating_fit_flat_when_harder_is_easier():
    rng = np.random.default_rng(3)
    ratings = rng.uniform(400, 2800, 2000)
    solved = (rng.uniform(size=2000) < (ratings - 400) / 2400).astype(float)
    assert m.rating_fit(ratings, solved, n_boot=50).bound == "flat"


def test_per_bin():
    bins = [0, 0, 1, 1, 1, 3]
    solved = [1, 0, 1, 1, 1, 0]
    rows = m.per_bin(bins, solved, 4)
    assert [r["n"] for r in rows] == [2, 3, 0, 1]
    assert rows[0]["solve"] == 0.5 and rows[1]["solve"] == 1.0 and math.isnan(rows[2]["solve"])


def test_pass_at_k():
    assert m.pass_at_k(8, 0, 1) == 0.0
    assert m.pass_at_k(8, 8, 8) == 1.0
    assert m.pass_at_k(8, 2, 1) == pytest.approx(0.25)
    assert m.pass_at_k(8, 1, 4) == pytest.approx(0.5)
    assert m.pass_at_k(8, 7, 2) == 1.0
    with pytest.raises(ValueError):
        m.pass_at_k(4, 1, 8)

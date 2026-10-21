"""Eval metrics (EVALS.md §2): rates with puzzle-level bootstrap CIs, paired
bootstrap, the puzzle-rating logistic fit, per-bin solve rates and pass@k.

Everything resamples **puzzles**, not positions: a 3-move puzzle's positions
are not independent. Position-level metrics (move accuracy, legal and format
rate) are ratios of per-puzzle sums, so the bootstrap keeps each puzzle's
positions together.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

N_BOOT = 10_000
SEED = 2026
ALPHA = 0.05
# The rating fit works on a standardised scale: x = (rating - centre) / scale.
_R_CENTRE, _R_SCALE = 1600.0, 400.0


@dataclass(frozen=True)
class CI:
    value: float
    lo: float
    hi: float

    def pct(self, digits: int = 1) -> str:
        return f"{100 * self.value:.{digits}f}% [{100 * self.lo:.{digits}f}, {100 * self.hi:.{digits}f}]"

    def as_dict(self) -> dict[str, float]:
        return {"value": self.value, "lo": self.lo, "hi": self.hi}


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _idx(n: int, n_boot: int, seed: int) -> np.ndarray:
    return _rng(seed).integers(0, n, size=(n_boot, n))


def _ci(point: float, boots: np.ndarray) -> CI:
    lo, hi = np.nanquantile(boots, [ALPHA / 2, 1 - ALPHA / 2])
    return CI(float(point), float(lo), float(hi))


def ratio_ci(
    num: Sequence[float], den: Sequence[float], n_boot: int = N_BOOT, seed: int = SEED
) -> CI:
    """sum(num) / sum(den) with a percentile bootstrap over the units (puzzles)."""
    a, b = np.asarray(num, float), np.asarray(den, float)
    if len(a) == 0 or b.sum() == 0:
        return CI(math.nan, math.nan, math.nan)
    idx = _idx(len(a), n_boot, seed)
    with np.errstate(invalid="ignore", divide="ignore"):
        boots = a[idx].sum(1) / b[idx].sum(1)
    return _ci(a.sum() / b.sum(), boots)


def mean_ci(values: Sequence[float], n_boot: int = N_BOOT, seed: int = SEED) -> CI:
    return ratio_ci(values, [1.0] * len(values), n_boot, seed)


def paired_diff_ci(
    a: Sequence[float], b: Sequence[float], n_boot: int = N_BOOT, seed: int = SEED
) -> CI:
    """mean(a) - mean(b) on the same puzzles, resampling puzzles jointly."""
    x, y = np.asarray(a, float), np.asarray(b, float)
    if x.shape != y.shape:
        raise ValueError("paired bootstrap needs the same puzzles in the same order")
    d = x - y
    idx = _idx(len(d), n_boot, seed)
    return _ci(float(d.mean()), d[idx].mean(1))


# --- puzzle-rating fit ------------------------------------------------------------


@dataclass(frozen=True)
class RatingFit:
    """Rating at which P(solve) crosses 50%. `bound` says why r50 is missing.

    `bound` is "above" when the fit never drops to 50% inside the rating range
    (strong model), "below" when it is under 50% everywhere (weak model) or no
    puzzle was solved, "flat" when P(solve) does not fall with rating.
    """

    r50: float | None
    lo: float | None = None
    hi: float | None = None
    slope_per_100: float | None = None  # change in log-odds per 100 rating points
    bound: str | None = None

    def text(self) -> str:
        if self.r50 is None:
            return {"above": "> range", "below": "< range"}.get(self.bound or "", "n/a")
        if self.lo is None or self.hi is None:
            return f"{self.r50:.0f}"
        return f"{self.r50:.0f} [{self.lo:.0f}, {self.hi:.0f}]"


def _logit_fit(x: np.ndarray, y: np.ndarray, iters: int = 50) -> tuple[float, float] | None:
    """Logistic regression y ~ a + b x by Newton's method, tiny ridge for stability."""
    a, b = 0.0, 0.0
    ridge = 1e-6
    for _ in range(iters):
        z = np.clip(a + b * x, -30, 30)
        p = 1 / (1 + np.exp(-z))
        w = p * (1 - p)
        g = np.array([(y - p).sum() - ridge * a, ((y - p) * x).sum() - ridge * b])
        h = np.array([[w.sum() + ridge, (w * x).sum()], [(w * x).sum(), (w * x * x).sum() + ridge]])
        try:
            step = np.linalg.solve(h, g)
        except np.linalg.LinAlgError:
            return None
        a, b = a + step[0], b + step[1]
        if np.abs(step).max() < 1e-9:
            break
    return float(a), float(b)


def _r50(
    fit: tuple[float, float] | None, lo_r: float, hi_r: float
) -> tuple[float | None, str | None]:
    if fit is None:
        return None, "flat"
    a, b = fit
    if b >= 0:
        return None, "flat"
    r = _R_CENTRE + _R_SCALE * (-a / b)
    if r > hi_r:
        return None, "above"
    if r < lo_r:
        return None, "below"
    return r, None


def rating_fit(
    ratings: ArrayLike,
    solved: ArrayLike,
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> RatingFit:
    """Fit P(solve) vs puzzle rating; CI from a bootstrap over puzzles.

    r50 must fall inside [min rating, max rating]; extrapolating a logistic
    beyond the data says little, so outside that the result is a bound.
    """
    r = np.asarray(ratings, float)
    y = np.asarray(solved, float)
    lo_r, hi_r = float(r.min()), float(r.max())
    if y.sum() == 0:
        return RatingFit(None, bound="below")
    if y.sum() == len(y):
        return RatingFit(None, bound="above")
    x = (r - _R_CENTRE) / _R_SCALE
    fit = _logit_fit(x, y)
    point, bound = _r50(fit, lo_r, hi_r)
    slope = None if fit is None else fit[1] / _R_SCALE * 100
    if point is None:
        return RatingFit(None, slope_per_100=slope, bound=bound)
    boots = []
    for row in _idx(len(y), n_boot, seed):
        v, _ = _r50(_logit_fit(x[row], y[row]), lo_r, hi_r)
        boots.append(math.nan if v is None else v)
    arr = np.asarray(boots)
    lo, hi = (None, None)
    if np.isfinite(arr).mean() >= 0.95:  # else the CI is not meaningful
        lo, hi = (float(v) for v in np.nanquantile(arr, [ALPHA / 2, 1 - ALPHA / 2]))
    return RatingFit(point, lo, hi, slope, None)


# --- per-bin and pass@k -----------------------------------------------------------


def per_bin(bins: Sequence[int], solved: Sequence[float], n_bins: int) -> list[dict[str, float]]:
    b = np.asarray(bins, int)
    y = np.asarray(solved, float)
    out = []
    for i in range(n_bins):
        m = b == i
        n = int(m.sum())
        out.append({"bin": i, "n": n, "solve": float(y[m].mean()) if n else math.nan})
    return out


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k from n samples with c correct (Chen et al., 2021)."""
    if k > n:
        raise ValueError(f"pass@{k} needs at least {k} samples, have {n}")
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)

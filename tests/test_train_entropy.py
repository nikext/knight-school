"""ADR-027: the entropy target set from the start's own entropy (config v4)."""

from __future__ import annotations

import pytest

from ks.train.grpo import NO_BONUS, StartTarget


def test_no_bonus_in_the_window_then_the_mean_capped_at_the_base_target():
    st = StartTarget(5, 0.2)
    assert st.target == NO_BONUS
    got = [st.step(i, e) for i, e in enumerate([0.15, 0.14, 0.13, 0.14, 0.14], start=1)]
    assert got[:4] == [None] * 4
    assert got[4] == pytest.approx(0.14) == st.target
    assert st.step(6, 0.01) is None and st.target == pytest.approx(0.14)  # fixed from here on


def test_a_start_above_the_cap_keeps_the_cap():
    st = StartTarget(5, 0.2)
    for i in range(1, 6):
        st.step(i, 0.88)
    assert st.target == 0.2


def test_zero_steps_is_the_fixed_target_of_v3():
    st = StartTarget(0, 0.2)
    assert st.target == 0.2 and st.step(1, 0.05) is None and st.target == 0.2


def test_a_resume_mid_window_carries_on():
    st = StartTarget(3, 0.2)
    st.step(1, 0.10)
    st.step(2, 0.12)
    again = StartTarget.from_state(st.state())
    assert again.target == NO_BONUS and again.window == [0.10, 0.12]
    assert again.step(3, 0.14) == pytest.approx(0.12)
    done = StartTarget.from_state(again.state())
    assert done.target == pytest.approx(0.12) and done.step(4, 0.3) is None

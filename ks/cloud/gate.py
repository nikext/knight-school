"""The pre-flight money gate (BUDGET.md §3.3). Pure: no I/O, no clock.

``check()`` answers one question: may this run (attempt) start now, given the
caps, the prices and everything already in the ledger? It collects *every*
reason to refuse rather than stopping at the first, so the user sees the
whole picture in one go.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from ks.cloud.config import Caps, Prices, RunConfig
from ks.cloud.ledger import LedgerState


@dataclass(frozen=True)
class Ok:
    worst_case_usd: float
    price_per_hour: float
    run_budget_usd: float
    lines: list[str] = field(default_factory=list)
    ok: Literal[True] = True


@dataclass(frozen=True)
class Refusal:
    reasons: list[str]
    lines: list[str] = field(default_factory=list)
    ok: Literal[False] = False


def hourly_price(run: RunConfig, prices: Prices) -> tuple[float | None, list[str]]:
    """Whole-VM spot $/h incl. boot disk, the max over the run's candidate regions."""
    reasons, hourly = [], []
    for region in run.regions():
        mp = prices.machine(region, run.machine)
        if mp is None:
            reasons.append(f"no spot price for {run.machine} in {region} in prices.yaml")
        else:
            hourly.append(mp.usd_per_hour)
    if reasons:
        return None, reasons
    return max(hourly) + prices.disk_usd_per_hour(run.boot_disk_gb), []


def worst_case(run: RunConfig, price_per_hour: float, caps: Caps) -> float:
    """Rounded *up* to 1/100 cent: a worst case never rounds in our favour."""
    raw = run.max_hours * price_per_hour * caps.limits.worst_case_factor
    return math.ceil(round(raw * 10_000, 6)) / 10_000


def check(
    run: RunConfig,
    caps: Caps,
    prices: Prices,
    ledger: LedgerState,
    *,
    now: datetime,
    attempt: int = 1,
    confirm: bool = False,
    use_contingency: bool = False,
) -> Ok | Refusal:
    lim = caps.limits
    reasons: list[str] = list(caps.problems())
    lines: list[str] = []

    # --- the machine and the job's hard limits -----------------------------
    if not prices.verified:
        reasons.append("prices.yaml is not verified (run `ks prices` and cross-check)")
    if prices.fetched_on is None:
        reasons.append("prices.yaml has no fetched_on date")
    elif now - prices.fetched_on > timedelta(days=lim.prices_max_age_days):
        age = (now - prices.fetched_on).days
        reasons.append(
            f"prices.yaml is {age} days old (max {lim.prices_max_age_days}); re-run `ks prices`"
        )

    if lim.spot_only and not run.spot:
        reasons.append("not spot: only spot VMs are allowed")
    if run.gpus > lim.max_gpus_per_job:
        reasons.append(f"{run.gpus} GPUs requested; at most {lim.max_gpus_per_job} per job")
    for region in run.regions():
        mp = prices.machine(region, run.machine)
        if mp is not None and mp.gpus != run.gpus:
            reasons.append(f"{run.machine} has {mp.gpus} GPUs but the run says gpus: {run.gpus}")
            break
    if not 0 < run.max_hours <= lim.max_hours_per_job:
        reasons.append(f"max_hours {run.max_hours} must be in (0, {lim.max_hours_per_job}]")

    if not run.id.startswith(run.milestone.lower() + "-"):
        reasons.append(f"run id {run.id!r} does not start with milestone {run.milestone!r}")

    pool = caps.pools.get(run.pool)
    if pool is None:
        reasons.append(f"unknown pool {run.pool!r}")
    if run.backend == "gce" and run.pool != "compute":
        reasons.append("the gce backend bills to the compute pool")
    if run.backend == "vertex" and not (
        pool and run.pool == "vertex" and pool.covers_custom_training
    ):
        reasons.append("Vertex custom training is not covered by the vertex credit (caps.yaml)")

    price, price_reasons = hourly_price(run, prices)
    reasons += price_reasons
    if price is None or pool is None:
        return Refusal(reasons=reasons, lines=lines)

    worst = worst_case(run, price, caps)
    lines.append(
        f"run {run.id} attempt {attempt}: {run.machine} spot in {', '.join(run.zones)}, "
        f"max {run.max_hours} h x ${price:.4f}/h x {lim.worst_case_factor} = worst case ${worst:.2f}"
    )

    # --- credit window ------------------------------------------------------
    if (start := pool.usable_from_at()) and now < start:
        reasons.append(f"pool {run.pool} may only be used from {start:%Y-%m-%d %H:%MZ}")
    if expires := pool.expires_at():
        deadline = expires - timedelta(hours=lim.expiry_margin_hours)
        end = now + timedelta(hours=run.max_hours)
        lines.append(
            f"credit {pool.credit!r} expires {pool.expires}; jobs must end by {deadline:%Y-%m-%d %H:%MZ}"
        )
        if end > deadline:
            reasons.append(
                f"worst-case end {end:%Y-%m-%d %H:%MZ} is after {deadline:%Y-%m-%d %H:%MZ} "
                f"({lim.expiry_margin_hours:g} h before the credit expires)"
            )

    # --- the credit itself (shared with the user's other projects) --------
    if pool.remaining_usd is None or pool.checked_on is None:
        reasons.append(f"pool {run.pool}: credit remaining was never read from Billing -> Credits")
    else:
        age = now - pool.checked_on
        if age > timedelta(days=lim.credit_check_max_age_days):
            reasons.append(
                f"pool {run.pool}: credit was last read {age.days} days ago "
                f"(max {lim.credit_check_max_age_days}); ask the user to re-read Billing -> Credits"
            )
        since = ledger.spent(run.pool, since=pool.checked_on)
        headroom = lim.credit_reserve_factor * pool.remaining_usd - since - ledger.running(run.pool)
        lines.append(
            f"credit headroom: {lim.credit_reserve_factor} x ${pool.remaining_usd:.2f} remaining "
            f"- ${since:.2f} spent since {pool.checked_on:%Y-%m-%d} - running = ${headroom:.2f}"
        )
        if worst > headroom + 1e-9:
            reasons.append(f"worst case ${worst:.2f} exceeds the credit headroom ${headroom:.2f}")

    # --- pool ceiling -------------------------------------------------------
    spent, running = ledger.spent(run.pool), ledger.running(run.pool)
    after = spent + running + worst
    lines.append(
        f"pool {run.pool}: ceiling ${pool.ceiling:.2f}, spent ${spent:.2f}, running ${running:.2f}, "
        f"after this ${after:.2f}, left ${pool.ceiling - after:.2f}"
    )
    if after > pool.ceiling + 1e-9:
        reasons.append(
            f"pool {run.pool} ceiling ${pool.ceiling:.2f} would be exceeded (${after:.2f})"
        )

    # --- milestone allocation ----------------------------------------------
    allocs = caps.allocations.get(run.pool, {})
    alloc = allocs.get(run.milestone)
    if alloc is None or run.milestone == "contingency":
        reasons.append(f"milestone {run.milestone!r} has no allocation in pool {run.pool}")
    else:
        used = ledger.spent(run.pool, run.milestone) + ledger.running(run.pool, run.milestone)
        lines.append(
            f"milestone {run.milestone}: allocation ${alloc:.2f}, used ${used:.2f}, "
            f"after this ${used + worst:.2f}"
        )
        if used + worst > alloc + 1e-9:
            if not use_contingency:
                reasons.append(
                    f"milestone {run.milestone} allocation ${alloc:.2f} would be exceeded "
                    f"(${used + worst:.2f}); needs --use-contingency, which needs the user's approval"
                )
            else:
                contingency = allocs.get("contingency", 0.0)
                overrun = ledger.overrun(run.pool, allocs, extra={run.milestone: worst})
                lines.append(
                    f"contingency: ${contingency:.2f}, total overrun after this ${overrun:.2f}"
                )
                if overrun > contingency + 1e-9:
                    reasons.append(
                        f"contingency ${contingency:.2f} would be exceeded (overrun ${overrun:.2f})"
                    )

    # --- one job at a time, and run identity --------------------------------
    for a in ledger.open_attempts(run.pool):
        reasons.append(
            f"{a.start.id} attempt {a.start.attempt} is still open in the ledger "
            "(one job at a time; run `ks reconcile`)"
        )

    previous = ledger.run_attempts(run.id)
    if attempt == 1:
        if previous:
            reasons.append(f"run id {run.id} is already in the ledger; use a new id")
        budget = run.run_budget_usd if run.run_budget_usd is not None else worst * run.max_attempts
    else:
        if not previous:
            reasons.append(f"attempt {attempt} of {run.id} but the run has no earlier attempt")
        elif previous[-1].start.attempt != attempt - 1:
            reasons.append(
                f"attempt {attempt} of {run.id} does not follow attempt {previous[-1].start.attempt}"
            )
        if attempt > run.max_attempts:
            reasons.append(f"attempt {attempt} exceeds max_attempts {run.max_attempts}")
        approved = previous[0].start.run_budget_usd if previous else None
        budget = approved if approved is not None else worst * run.max_attempts
    run_spent, run_running = ledger.run_cost(run.id)
    lines.append(
        f"run budget: ${budget:.2f} approved, ${run_spent:.2f} spent, "
        f"after this ${run_spent + run_running + worst:.2f}"
    )
    if run_spent + run_running + worst > budget + 1e-9:
        reasons.append(
            f"run budget ${budget:.2f} would be exceeded (${run_spent + run_running + worst:.2f})"
        )

    if not confirm:
        reasons.append("--confirm missing (pass it only after the user said yes in this session)")

    if reasons:
        return Refusal(reasons=reasons, lines=lines)
    return Ok(
        worst_case_usd=worst,
        price_per_hour=round(price, 6),
        run_budget_usd=round(budget, 4),
        lines=lines,
    )

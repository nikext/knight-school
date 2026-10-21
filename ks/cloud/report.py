"""`ks costs`: ledger totals per pool and per milestone against the caps."""

from __future__ import annotations

from datetime import datetime, timedelta

from ks.cloud.config import Caps
from ks.cloud.ledger import LedgerState


def costs_report(caps: Caps, ledger: LedgerState, now: datetime) -> list[str]:
    lim = caps.limits
    lines = [f"costs as of {now:%Y-%m-%d %H:%MZ} (USD)", ""]
    lines.append(f"{'pool':<8} {'ceiling':>8} {'spent':>8} {'running':>8} {'left':>8}   credit")
    for name, pool in caps.pools.items():
        spent, running = ledger.spent(name), ledger.running(name)
        credit = []
        if pool.remaining_usd is not None and pool.checked_on is not None:
            since = ledger.spent(name, since=pool.checked_on)
            headroom = lim.credit_reserve_factor * pool.remaining_usd - since - running
            stale = now - pool.checked_on > timedelta(days=lim.credit_check_max_age_days)
            credit.append(
                f"${pool.remaining_usd:.2f} left on {pool.checked_on:%Y-%m-%d}"
                f"{' (STALE: re-read Billing -> Credits)' if stale else ''}, headroom ${headroom:.2f}"
            )
        if expires := pool.expires_at():
            deadline = expires - timedelta(hours=lim.expiry_margin_hours)
            days = (deadline - now).total_seconds() / 86400
            credit.append(f"jobs must end by {deadline:%Y-%m-%d} ({days:.1f} days)")
        if (start := pool.usable_from_at()) and now < start:
            credit.append(f"locked until {pool.usable_from}")
        lines.append(
            f"{name:<8} {pool.ceiling:>8.2f} {spent:>8.2f} {running:>8.2f} "
            f"{pool.ceiling - spent - running:>8.2f}   {'; '.join(credit)}"
        )
    for name in caps.pools:
        allocs = caps.allocations[name]
        lines += [
            "",
            f"{name} by milestone",
            f"{'':<12} {'alloc':>8} {'spent':>8} {'running':>8} {'left':>8}",
        ]
        for m, alloc in allocs.items():
            if m == "contingency":
                used = ledger.overrun(name, allocs)
                lines.append(
                    f"{m:<12} {alloc:>8.2f} {used:>8.2f} {'':>8} {alloc - used:>8.2f}   (overruns)"
                )
                continue
            spent, running = ledger.spent(name, m), ledger.running(name, m)
            flag = "  OVER" if spent + running > alloc + 1e-9 else ""
            lines.append(
                f"{m:<12} {alloc:>8.2f} {spent:>8.2f} {running:>8.2f} {alloc - spent - running:>8.2f}{flag}"
            )
    open_ = ledger.open_attempts()
    lines += ["", f"open attempts: {len(open_)}"] + [
        f"  {a.start.id} attempt {a.start.attempt}: worst case ${a.start.worst_case_usd:.2f}"
        for a in open_
    ]
    return lines

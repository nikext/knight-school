"""The `ks` command line. Money commands live under ks.cloud."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ks.cloud import config as cfg

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Knight School tooling.")


def _env(*keys: str) -> dict[str, str]:
    env = cfg.read_env()
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise typer.BadParameter(f"set {', '.join(missing)} in .env")
    return env


def _ops():
    from ks.cloud.gcp import GcloudOps

    return GcloudOps(_env("GOOGLE_CLOUD_PROJECT")["GOOGLE_CLOUD_PROJECT"])


def _echo(lines: list[str]) -> None:
    for line in lines:
        typer.echo(line)


@app.command()
def costs() -> None:
    """Ledger totals per pool and milestone against the caps."""
    from ks.cloud.ledger import load_state
    from ks.cloud.report import costs_report

    _echo(costs_report(cfg.load_caps(), load_state(), cfg.utcnow()))


@app.command()
def prices() -> None:
    """Fetch spot prices from the Catalog API into costs/prices.yaml (verified: false)."""
    from ks.cloud.prices import fetch

    doc = fetch(_env("GOOGLE_CLOUD_PROJECT")["GOOGLE_CLOUD_PROJECT"], cfg.utcnow())
    for region, table in doc["gce_spot"].items():
        for machine, p in table.items():
            typer.echo(f"{region:<14} {machine:<16} ${p['usd_per_hour']:.4f}/h")
    typer.echo(f"disk pd-balanced ${doc['disk']['pd-balanced_usd_per_gb_month']}/GB-month")
    typer.echo(
        "written with verified: false -- cross-check one machine with the user, then set verified: true"
    )


@app.command()
def launch(
    run_config: Path,
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Only after the user said yes in this session.")
    ] = False,
    use_contingency: Annotated[
        bool,
        typer.Option("--use-contingency", help="Book an approved overrun against contingency."),
    ] = False,
    watch: Annotated[bool, typer.Option("--watch", help="Follow the run until it ends.")] = False,
    interval: float = 300,
) -> None:
    """Gate a run and, with --confirm, start it. Without --confirm it only shows the gate."""
    from ks.cloud.launch import launch as do_launch

    env = _env("GOOGLE_CLOUD_PROJECT", "BUCKET", "RUNNER_SA")
    run = cfg.load_run(run_config)
    caps, prices_ = cfg.load_caps(), cfg.load_prices()
    approved = f"user, in session {cfg.utcnow():%Y-%m-%d}" if confirm else ""
    res = do_launch(
        run,
        caps=caps,
        prices=prices_,
        ops=_ops(),
        now=cfg.utcnow().replace(microsecond=0),
        bucket=env["BUCKET"],
        runner_sa=env["RUNNER_SA"],
        confirm=confirm,
        use_contingency=use_contingency,
        approved=approved,
    )
    _echo(res.lines)
    if not res.ok:
        raise typer.Exit(2)
    if watch:
        _watch(run, interval, approved)


def _watch(run: cfg.RunConfig, interval: float, approved: str) -> None:
    from ks.cloud.watch import watch as do_watch

    env = _env("GOOGLE_CLOUD_PROJECT", "BUCKET", "RUNNER_SA")
    status = do_watch(
        run,
        caps=cfg.load_caps(),
        prices=cfg.load_prices(),
        ops=_ops(),
        bucket=env["BUCKET"],
        runner_sa=env["RUNNER_SA"],
        approved=approved,
        interval=interval,
        log=lambda s: typer.echo(s),
    )
    typer.echo(f"{run.id}: final status {status}")
    if status not in ("done",):
        raise typer.Exit(1)


@app.command()
def watch(run_config: Path, interval: float = 300) -> None:
    """Follow an already launched run (preemption retries go through the gate)."""
    from ks.cloud.ledger import load_state

    run = cfg.load_run(run_config)
    atts = load_state().run_attempts(run.id)
    approved = atts[0].start.approved if atts else ""
    _watch(run, interval, approved)


@app.command()
def reconcile() -> None:
    """Close finished attempts in the ledger with their actual cost."""
    from ks.cloud.reconcile import reconcile as do_reconcile

    env = _env("BUCKET")
    _echo(do_reconcile(_ops(), env["BUCKET"], cfg.utcnow().replace(microsecond=0)))


@app.command()
def sweep(delete: Annotated[bool, typer.Option("--delete")] = False) -> None:
    """List everything that can bill by the hour; --delete removes ours."""
    from ks.cloud.sweep import sweep as do_sweep

    lines, _ = do_sweep(_ops(), delete=delete)
    _echo(lines)


@app.command()
def charge(
    id: Annotated[str, typer.Option()],
    milestone: Annotated[str, typer.Option()],
    pool: Annotated[str, typer.Option()],
    kind: Annotated[str, typer.Option()],
    usd: Annotated[float, typer.Option()],
    note: Annotated[str, typer.Option()] = "",
) -> None:
    """Book a cost with no lifetime (a Gemini call, a month of storage) in the ledger."""
    from ks.cloud.ledger import ChargeEvent, append_event, now_ts

    caps = cfg.load_caps()
    if pool not in caps.pools or milestone not in caps.allocations[pool]:
        raise typer.BadParameter(f"unknown pool/milestone {pool}/{milestone}")
    fields = dict(ts=now_ts(), id=id, milestone=milestone, pool=pool, kind=kind, actual_usd=usd)
    append_event(ChargeEvent.model_validate(fields | ({"note": note} if note else {})))
    typer.echo(f"ledger: charge {id} ${usd:.4f} to {pool}/{milestone}")


@app.command()
def data(
    steps: Annotated[list[str] | None, typer.Argument(help="Steps to run; default: all.")] = None,
    force: Annotated[bool, typer.Option("--force", help="Rebuild even if unchanged.")] = False,
) -> None:
    """Build the M1 datasets (DATA.md). Steps whose inputs and code are unchanged are skipped."""
    from ks.data.build import STEPS, run

    chosen = steps or list(STEPS)
    unknown = [s for s in chosen if s not in STEPS]
    if unknown:
        raise typer.BadParameter(f"unknown steps {unknown}; known: {list(STEPS)}")
    run(chosen, log=lambda s: typer.echo(s, err=True), force=force)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

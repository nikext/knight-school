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


@app.command("eval")
def eval_(
    model: Annotated[str, typer.Argument(help="Profile name in configs/models/ or a YAML path.")],
    set_name: Annotated[
        str, typer.Option("--set", help="dev500, test2000, test500, chessbench1k, probe500.")
    ] = "dev500",
    limit: Annotated[
        int | None, typer.Option(help="Only this many puzzles, spread over the bins.")
    ] = None,
    n: Annotated[int, typer.Option(help="Samples per prompt (pass@k on dev only).")] = 1,
    max_usd: Annotated[float | None, typer.Option("--max-usd", help="Stop at this cost.")] = None,
    ckpt: Annotated[
        str | None, typer.Option(help="Local dir or gs:// checkpoint instead of the HF repo.")
    ] = None,
    run_name: Annotated[
        str | None, typer.Option("--run", help="Report name; default: the profile name.")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Results dir; default results/eval.")] = None,
    milestone: Annotated[str, typer.Option(help="Ledger milestone for Gemini charges.")] = "M2",
) -> None:
    """Run the eval harness and write results/eval/<set>/<run>.{json,md} (EVALS.md §3)."""
    from ks.eval import backends, harness, probe, report, sets
    from ks.eval import profile as prof

    p = prof.load(model)
    if n > 1 and set_name.startswith("test"):
        raise typer.BadParameter("pass@k sampling is for dev sets only (EVALS.md §2)")
    if p.backend == "gemini" and max_usd is None:
        raise typer.BadParameter("Gemini runs need --max-usd")
    model_path = _fetch_ckpt(ckpt) if ckpt else None
    if p.backend == "gemini":
        from ks.eval.gemini import GeminiBackend

        backend: backends.Backend = GeminiBackend(p, milestone=milestone, max_usd=max_usd)
    else:
        backend = backends.make(p, model_path)
    name = run_name or p.name
    log = lambda s: typer.echo(f"[eval {name}] {s}", err=True)  # noqa: E731
    try:
        if set_name in sets.PROBE_SETS:
            rows = sets.spread(sets.load_probe().to_dicts(), limit)
            result = probe.run(p, rows, backend)
            result["header"]["run"] = name
            result["header"]["checkpoint"] = ckpt
            paths = report.write(result, out or report.RESULTS_DIR, probe.markdown)
        else:
            puzzles = sets.spread(sets.load_puzzles(set_name), limit)
            cfg_ = harness.EvalRun(p, set_name, puzzles, n, max_usd, ckpt, name, log)
            result = harness.run(cfg_, backend)
            paths = report.write(result, out or report.RESULTS_DIR)
    finally:
        charge = getattr(backend, "ledger_charge", None)
        if charge is not None:
            charge(f"{milestone.lower()}-gemini-{name}")
        backend.close()
    for path in paths:
        typer.echo(str(path))
    typer.echo(paths[1].read_text())


@app.command("primer-tokens")
def primer_tokens(
    model: Annotated[str, typer.Argument(help="Profile of the chosen main model.")],
) -> None:
    """Count primer S/M tokens with the model's tokenizer and record them in the manifests."""
    from ks.data.tokens import count, write_manifests

    counts = count(model)
    write_manifests(counts)
    for name, c in counts.items():
        typer.echo(
            f"primer-{name}: {c['examples']:,} examples, {c['total']:,} tokens, {c['answer']:,} answer tokens"
        )


def _fetch_ckpt(ckpt: str) -> str:
    """A gs:// checkpoint is copied to a local temp dir; a local path is used as is."""
    if not ckpt.startswith("gs://"):
        return ckpt
    import tempfile

    from google.cloud import storage

    bucket_name, _, prefix = ckpt.removeprefix("gs://").partition("/")
    prefix = prefix.rstrip("/") + "/"
    dest = Path(tempfile.mkdtemp(prefix="ks-ckpt-"))
    for blob in storage.Client().list_blobs(bucket_name, prefix=prefix):
        target = dest / blob.name.removeprefix(prefix)
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(target))
    return str(dest)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

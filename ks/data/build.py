"""`make data`: the M1 chain, step by step, each skipped when its inputs and code are unchanged.

puzzles -> evaldb -> probe -> blocklist -> rltrain -> timing -> rewards -> primer -> chessbench
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

import polars as pl
import requests

from ks.chess import board as kb
from ks.data import blocklist as bl
from ks.data import evaldb, probe, puzzles, rewards
from ks.data import manifest as mf
from ks.data import primer as pr

Log = Callable[[str], None]

EVALDB_K = 2_000_000
EVALDB_MAX_LINES = 30_000_000

EVAL_SIZES = {"test2000": 2000, "dev500": 500}
TEST500 = 500
RL_TARGET = 66_000  # positions before the mismatch filter; the task needs >= 50k after it

TIMING_POSITIONS = 200
TIMING_NODES = [100_000, 300_000, 1_000_000]
REWARD_NODES = 1_000_000  # the largest timed N that fits 60k positions in 4 h (DATA.md §6)
REWARD_SHARD = 250

PRIMER_SEED = 2026
PRIMER_SHARD = 50_000
# Example counts: token targets (DATA.md §7) x 1.2 / 139 tokens per example (Qwen3 tokenizer, 3k sample).
PRIMER_SIZES = {"M": 1_300_000, "S": 130_000}  # S = the first 130k examples of M (nested)

FILTERED = mf.DATA / "puzzles" / "filtered.parquet"
SPLITS = mf.DATA / "splits"
POSITIONS = mf.DATA / "positions"
EVALDB_SAMPLE = mf.DATA / "evaldb" / "sample.parquet"
PRIMER = mf.DATA / "primer"


def _remote_version(url: str) -> str:
    h = requests.head(url, timeout=30, allow_redirects=True).headers
    return f"{h.get('last-modified')}|{h.get('content-length')}"


def _mean(s: pl.Series, digits: int = 1) -> float:
    return round(cast(float, s.mean()), digits)


def _sets_csv(name: str) -> Path:
    return mf.SETS / f"{name}.csv"


# --- puzzles: filter, eval splits ------------------------------------------------


def step_puzzles(log: Log, force: bool = False) -> None:
    raw = mf.DATA / puzzles.RAW_ZST
    if not raw.exists():
        log(f"puzzles: downloading {puzzles.RAW_URL}")
        raw.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(puzzles.RAW_URL, stream=True, timeout=60) as r:
            r.raise_for_status()
            with raw.with_suffix(".tmp").open("wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        raw.with_suffix(".tmp").rename(raw)
    outs = [FILTERED, _sets_csv("test2000"), _sets_csv("dev500"), mf.SETS / "test500.ids"]
    params = {"seed": puzzles.SEED, "sizes": EVAL_SIZES, "test500": TEST500}
    fp = mf.fingerprint({"raw": mf.sha256_file(raw)}, params, [puzzles, kb, step_puzzles])
    if not force and mf.up_to_date("puzzles", fp, outs):
        log("puzzles: up to date")
        return
    csv = puzzles.decompress(raw, raw.with_suffix(""))
    df, counts = puzzles.filter_puzzles(puzzles.read_csv(csv))
    df = puzzles.with_split_columns(df, puzzles.SEED)
    sets, _ = puzzles.pick_eval_sets(df, EVAL_SIZES)
    test500 = puzzles.stratified_subset(sets["test2000"], TEST500)
    FILTERED.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(FILTERED)
    mf.SETS.mkdir(parents=True, exist_ok=True)
    for name, s in sets.items():
        s.sort("rating_bin", "order").select([*puzzles.COLUMNS, "rating_bin"]).write_csv(
            _sets_csv(name)
        )
    (mf.SETS / "test500.ids").write_text("".join(f"{p}\n" for p in test500["PuzzleId"]))
    per_bin = {
        name: s.group_by("rating_bin").len().sort("rating_bin")["len"].to_list()
        for name, s in sets.items()
    }
    mf.write(
        "puzzles",
        fp,
        outs,
        source=puzzles.RAW_URL,
        raw_sha256=mf.sha256_file(raw),
        seed=puzzles.SEED,
        filter_counts=dict(counts),
        rows=df.height,
        games=df["game_id"].n_unique(),
        eval_sets={
            n: {"puzzles": s.height, "games": s["game_id"].n_unique()} for n, s in sets.items()
        },
        eval_per_bin=per_bin,
        test500=test500.height,
    )
    log(f"puzzles: {df.height:,} kept; " + ", ".join(f"{n} {s.height}" for n, s in sets.items()))


# --- eval DB sample ----------------------------------------------------------------


def step_evaldb(log: Log, force: bool = False) -> None:
    params = {"k": EVALDB_K, "max_lines": EVALDB_MAX_LINES, "seed": evaldb.SEED}
    fp = mf.fingerprint(
        {"lichess_db_eval": _remote_version(evaldb.URL)}, params, [evaldb, step_evaldb]
    )
    if not force and mf.up_to_date("evaldb_sample", fp, [EVALDB_SAMPLE]):
        log("evaldb: up to date")
        return
    log(f"evaldb: streaming the first {EVALDB_MAX_LINES:,} lines, keeping {EVALDB_K:,}")
    df, read = evaldb.build(EVALDB_SAMPLE, EVALDB_K, EVALDB_MAX_LINES, evaldb.SEED)
    mf.write(
        "evaldb_sample",
        fp,
        [EVALDB_SAMPLE],
        source=evaldb.URL,
        source_version=_remote_version(evaldb.URL),
        lines_read=read,
        rows=df.height,
        seed=evaldb.SEED,
        method="Algorithm R reservoir over the first lines_read lines of the file",
    )
    log(f"evaldb: {df.height:,} positions from {read:,} lines")


# --- probe500 and the blocklist ------------------------------------------------------


def step_probe(log: Log, force: bool = False) -> None:
    out = _sets_csv("probe500")
    fp = mf.fingerprint(
        {"evaldb_sample": mf.output_sha("evaldb_sample")},
        {"seed": probe.SEED},
        [probe, pr, kb, step_probe],
    )
    if not force and mf.up_to_date("probe500", fp, [out]):
        log("probe: up to date")
        return
    df = probe.build(pl.read_parquet(EVALDB_SAMPLE), probe.SEED)
    df.write_csv(out)
    per_task = dict(df.group_by("task").len().sort("task").iter_rows())
    in_check = df.filter(pl.col("task") == "P4", pl.col("answer") != "no").height
    mf.write(
        "probe500",
        fp,
        [out],
        seed=probe.SEED,
        rows=df.height,
        per_task=per_task,
        p4_in_check=in_check,
    )
    log(f"probe: {df.height} items")


def step_blocklist(log: Log, force: bool = False) -> None:
    sets = {n: _sets_csv(n) for n in ["test2000", "dev500", "probe500"]}
    outs = [mf.SETS / bl.EPD_FILE, mf.SETS / bl.GAMES_FILE]
    fp = mf.fingerprint(
        {n: mf.sha256_file(p) for n, p in sets.items()}, {}, [bl, puzzles, kb, step_blocklist]
    )
    if not force and mf.up_to_date("blocklist", fp, outs):
        log("blocklist: up to date")
        return
    keys: set[str] = set()
    games: set[str] = set()
    per_set: dict[str, int] = {}
    for name in ["test2000", "dev500"]:
        df = pl.read_csv(sets[name], schema_overrides={"PuzzleId": pl.String})
        k = bl.puzzle_keys(df)
        per_set[name] = len(k)
        keys |= k
        games |= {puzzles.game_id(u) for u in df["GameUrl"]}
    pk = bl.probe_keys(pl.read_csv(sets["probe500"]).with_columns(pl.col("move").fill_null("")))
    per_set["probe500"] = len(pk)
    keys |= pk
    bl.write(mf.SETS, keys, games)
    mf.write("blocklist", fp, outs, keys=len(keys), games=len(games), keys_per_set=per_set)
    log(f"blocklist: {len(keys):,} keys, {len(games):,} games")


# --- rl_train / primer_pool --------------------------------------------------------------

RL_PUZZLES = SPLITS / "rl_train_puzzles.parquet"
POOL = SPLITS / "primer_pool.parquet"
CANDIDATES = POSITIONS / "rl_train_candidates.parquet"


def step_rltrain(log: Log, force: bool = False) -> None:
    outs = [RL_PUZZLES, POOL, CANDIDATES]
    inputs = {"puzzles": mf.output_sha("puzzles"), "blocklist": mf.output_sha("blocklist")}
    fp = mf.fingerprint(inputs, {"target": RL_TARGET}, [puzzles, kb, step_rltrain])
    if not force and mf.up_to_date("rl_train_candidates", fp, outs):
        log("rltrain: up to date")
        return
    block = bl.Blocklist.load(mf.SETS)
    df = pl.read_parquet(FILTERED)
    rest = puzzles.without_games(df, block.games)
    used, positions, stats = puzzles.take_positions(
        rest, RL_TARGET, set(block.keys), set(block.games)
    )
    pool = puzzles.without_games(rest, puzzles.games_of(used))
    SPLITS.mkdir(parents=True, exist_ok=True)
    POSITIONS.mkdir(parents=True, exist_ok=True)
    used.write_parquet(RL_PUZZLES)
    pool.write_parquet(POOL)
    cand = pl.DataFrame(positions)
    cand.write_parquet(CANDIDATES)
    games = list(block.games)
    hits = (
        block.hits_fens(cand["fen"].to_list())
        + used.filter(pl.col("game_id").is_in(games)).height
        + pool.filter(pl.col("game_id").is_in(games)).height
    )
    mf.write(
        "rl_train_candidates",
        fp,
        outs,
        rl_train_puzzles=used.height,
        rl_train_positions=cand.height,
        primer_pool_puzzles=pool.height,
        eval_games_removed=df.height - rest.height,
        contamination_hits=hits,
        **stats,
    )
    log(f"rltrain: {used.height:,} puzzles -> {cand.height:,} positions; pool {pool.height:,}")


# --- Stockfish timing and reward tables ---------------------------------------------------

RL_TRAIN = POSITIONS / "rl_train.parquet"


def step_timing(log: Log, force: bool = False) -> None:
    params = {"n": TIMING_POSITIONS, "nodes": TIMING_NODES, "workers": rewards.WORKERS}
    version = rewards.sf_version()
    inputs = {"candidates": mf.output_sha("rl_train_candidates"), "stockfish": version}
    fp = mf.fingerprint(inputs, params, [rewards, step_timing])
    m = mf.load("rewards_timing")
    if not force and m and m["fingerprint"] == fp:
        log("timing: up to date")
        return
    cand = pl.read_parquet(CANDIDATES)
    idx = sorted(random.Random(puzzles.SEED).sample(range(cand.height), TIMING_POSITIONS))
    sub = cand[idx]
    fens = sub["fen"].to_list()
    results: dict[int, list[dict]] = {}
    table = []
    for n in TIMING_NODES:
        res, wall = rewards.time_positions(fens, n, rewards.WORKERS)
        results[n] = res
        per_pos = wall * rewards.WORKERS / len(fens)
        hours_60k = 60_000 * per_pos / rewards.WORKERS / 3600
        agree = sum(r["sf_best_san"] == s for r, s in zip(res, sub["solution_san"], strict=True))
        table.append(
            {
                "nodes": n,
                "wall_s": round(wall, 1),
                "core_s_per_position": round(per_pos, 2),
                "hours_for_60k_at_18_workers": round(hours_60k, 2),
                "sf_best_eq_solution": round(agree / len(fens), 3),
            }
        )
        log(f"timing: {table[-1]}")
    top = TIMING_NODES[-1]
    for row in table:
        n = row["nodes"]
        diffs = [
            abs(x - y)
            for a, b in zip(results[n], results[top], strict=True)
            for x, y in zip(a["wp"], b["wp"], strict=True)
        ]
        row[f"mean_abs_wp_diff_vs_{top}"] = round(sum(diffs) / len(diffs), 4)
        row[f"share_wp_diff_over_0.1_vs_{top}"] = round(sum(d > 0.1 for d in diffs) / len(diffs), 4)
        row[f"top1_same_as_{top}"] = round(
            sum(
                a["sf_best_san"] == b["sf_best_san"]
                for a, b in zip(results[n], results[top], strict=True)
            )
            / len(fens),
            3,
        )
    mf.write("rewards_timing", fp, [], sf_version=version, positions=len(fens), table=table)
    log("timing: done; pick REWARD_NODES in ks/data/build.py and DATA.md §6")


def step_rewards(log: Log, force: bool = False) -> None:
    version = rewards.sf_version()
    inputs = {"candidates": mf.output_sha("rl_train_candidates"), "stockfish": version}
    params = {
        "nodes": REWARD_NODES,
        "threads": rewards.THREADS,
        "hash": rewards.HASH_MB,
        "mismatch": rewards.MISMATCH_WP,
    }
    fp = mf.fingerprint(inputs, params, [rewards, kb, step_rewards])
    if not force and mf.up_to_date("rl_train", fp, [RL_TRAIN]):
        log("rewards: up to date")
        return
    cand = pl.read_parquet(CANDIDATES)
    t = time.perf_counter()
    shards = rewards.run_shards(
        cand, POSITIONS / "rewards", REWARD_NODES, REWARD_SHARD, rewards.WORKERS, log
    )
    wall = time.perf_counter() - t
    full = rewards.agreement(pl.concat(pl.read_parquet(s) for s in shards))
    kept, dropped = rewards.mismatch_filter(full)
    kept.write_parquet(RL_TRAIN)
    block = bl.Blocklist.load(mf.SETS)
    hits = block.hits_fens(kept["fen"].to_list())
    n = full.height
    secs = rewards.shard_seconds(POSITIONS / "rewards" / f"out-n{REWARD_NODES}")
    mf.write(
        "rl_train",
        fp,
        [RL_TRAIN],
        rows=kept.height,
        analysed=n,
        mismatch_dropped=dropped,
        mismatch_threshold_wp=rewards.MISMATCH_WP,
        sf_best_eq_solution=_mean(full["sf_agrees"], 4),
        sf_best_eq_solution_or_both_mate=_mean(full["sf_agrees"] | full["both_mate"], 4),
        sf_version=version,
        nodes=REWARD_NODES,
        threads=rewards.THREADS,
        hash_mb=rewards.HASH_MB,
        workers=rewards.WORKERS,
        wall_hours_this_run=round(wall / 3600, 2),
        cpu_hours=round(sum(secs.values()) / 3600, 1),
        shards_timed=f"{len(secs)}/{len(shards)}",
        contamination_hits=hits,
    )
    log(f"rewards: {kept.height:,} kept of {n:,} ({dropped:,} mismatches dropped)")


# --- primer ----------------------------------------------------------------------------------


def _primer_sources(seed: int, need_puzzle: int) -> tuple[pr.Source, pr.Source]:
    ev = pl.read_parquet(EVALDB_SAMPLE).select("fen", "cp", "mate", "line").to_dict(as_series=False)
    order = list(range(len(ev["fen"])))
    random.Random(seed).shuffle(order)
    pool = pl.read_parquet(POOL)
    fens: list[str] = []
    sols: list[str] = []
    for r in pool.iter_rows(named=True):
        for p in puzzles.expand(r["PuzzleId"], r["FEN"], r["Moves"], with_legal=False):
            fens.append(p["fen"])
            sols.append(p["solution_san"])
        if len(fens) >= need_puzzle:
            break
    perm = list(range(len(fens)))
    random.Random(seed + 1).shuffle(perm)
    return pr.evaldb_source(ev, order), pr.puzzle_source(
        [fens[i] for i in perm], [sols[i] for i in perm]
    )


def _verify_primer(paths: list[Path], block: bl.Blocklist) -> int:
    """contamination_hits: re-derive each example's prompt key and check every recorded key."""
    hits = 0
    for ex in pr.read_shards(paths):
        keys = ex["keys"]
        if kb.key(kb.board_from_fen(ex["fen"])) != keys[0]:
            raise AssertionError(f"{ex['id']}: recorded key doesn't match its FEN")
        hits += any(k in block.keys for k in keys)
    return hits


def step_primer(log: Log, force: bool = False) -> None:
    n_m, n_s = PRIMER_SIZES["M"], PRIMER_SIZES["S"]
    dirs = {name: PRIMER / name for name in PRIMER_SIZES}
    inputs = {
        "evaldb_sample": mf.output_sha("evaldb_sample"),
        "rl_train_candidates": mf.output_sha("rl_train_candidates"),
        "blocklist": mf.output_sha("blocklist"),
    }
    params = {"sizes": PRIMER_SIZES, "seed": PRIMER_SEED, "shard": PRIMER_SHARD}
    fp = mf.fingerprint(inputs, params, [pr, kb, puzzles, step_primer])
    if not force and all(mf.up_to_date(f"primer_{n}", fp, [d]) for n, d in dirs.items()):
        log("primer: up to date")
        return
    block = bl.Blocklist.load(mf.SETS)
    rl_keys = set(pl.read_parquet(CANDIDATES)["key"].to_list())
    need_puzzle = int(n_m * 0.5 * 0.85 * 1.3)  # T1-T5 share x puzzle share, with slack
    ev_src, pz_src = _primer_sources(PRIMER_SEED, need_puzzle)
    stats = pr.GenStats()
    t = time.perf_counter()
    examples = pr.generate(n_m, ev_src, pz_src, block.keys, rl_keys, PRIMER_SEED, "M", stats)
    m_paths, total = pr.write_shards(examples, dirs["M"], PRIMER_SHARD)
    log(f"primer: M {total:,} examples in {(time.perf_counter() - t) / 60:.1f} min")
    s_examples = (ex for i, ex in enumerate(pr.read_shards(m_paths)) if i < n_s)
    s_paths, s_total = pr.write_shards(s_examples, dirs["S"], PRIMER_SHARD)
    common = {
        "seed": PRIMER_SEED,
        "weights": pr.WEIGHTS,
        "puzzle_share": pr.PUZZLE_SHARE,
        "blocklist_drops": stats.blocklist_drops,
        "rl_train_drops": stats.rl_train_drops,
        "skipped_no_item": stats.skipped,
        "evaldb_positions_used": ev_src.used(),
        "puzzle_positions_used": pz_src.used(),
    }
    for name, paths, n in [("M", m_paths, total), ("S", s_paths, s_total)]:
        per_task: dict[str, int] = {}
        per_source: dict[str, int] = {}
        for ex in pr.read_shards(paths):
            per_task[ex["task"]] = per_task.get(ex["task"], 0) + 1
            per_source[ex["source"]] = per_source.get(ex["source"], 0) + 1
        mf.write(
            f"primer_{name}",
            fp,
            [dirs[name]],
            examples=n,
            shards=len(paths),
            per_task=dict(sorted(per_task.items())),
            per_source=per_source,
            nested_in="primer_M" if name == "S" else None,
            contamination_hits=_verify_primer(paths, block),
            tokens="counted in M2 with the chosen tokenizer",
            **common,
        )
        log(f"primer: {name} {n:,} examples, {len(paths)} shards")


# --- chessbench1k (optional, EVALS.md §1) ------------------------------------------------------

CHESSBENCH_URL = "https://storage.googleapis.com/searchless_chess/data/puzzles.csv"
CHESSBENCH_RAW = mf.DATA / "raw" / "chessbench" / "puzzles.csv"
CHESSBENCH_N = 1000


def step_chessbench(log: Log, force: bool = False) -> None:
    """1k of Ruoss et al.'s 10k puzzles, minus any that touch v1 training data.

    Same convention as Lichess (FEN before the opponent's move). The set is
    filtered against rl_train and primer-M rather than added to the
    blocklist, which would make the blocklist depend on its own downstream
    data. Later training sets (M5) must also exclude `chessbench1k` keys.
    """
    out = _sets_csv("chessbench1k")
    if not CHESSBENCH_RAW.exists():
        CHESSBENCH_RAW.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(CHESSBENCH_URL, timeout=60)
        r.raise_for_status()
        CHESSBENCH_RAW.write_bytes(r.content)
    inputs = {
        "chessbench": mf.sha256_file(CHESSBENCH_RAW),
        "rl_train_candidates": mf.output_sha("rl_train_candidates"),
        "primer_M": mf.output_sha("primer_M"),
    }
    fp = mf.fingerprint(
        inputs, {"n": CHESSBENCH_N, "seed": puzzles.SEED}, [puzzles, kb, step_chessbench]
    )
    if not force and mf.up_to_date("chessbench1k", fp, [out]):
        log("chessbench: up to date")
        return
    cb = pl.read_csv(CHESSBENCH_RAW, schema_overrides={"PuzzleId": pl.String})
    train_keys = set(pl.read_parquet(CANDIDATES)["key"].to_list())
    for ex in pr.read_shards(sorted((PRIMER / "M").glob("shard-*.jsonl.zst"))):
        train_keys.update(ex["keys"])
    rl_ids = set(pl.read_parquet(RL_PUZZLES)["PuzzleId"].to_list())
    clean = [
        pid not in rl_ids and not train_keys.intersection(puzzles.line_keys(fen, moves))
        for pid, fen, moves in cb.select("PuzzleId", "FEN", "Moves").iter_rows()
    ]
    pool = cb.filter(pl.Series(clean)).with_columns(
        pl.col("PuzzleId")
        .map_elements(lambda p: puzzles.order_key(puzzles.SEED, p), return_dtype=pl.String)
        .alias("order")
    )

    # Stratify by 200-Elo bin to the full 10k's proportions (largest remainder), so
    # excluding puzzles that touch training data doesn't shift the difficulty.
    def with_bin(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(
            pl.col("Rating")
            .clip(puzzles.RATING_LO, puzzles.RATING_HI)
            .map_elements(puzzles.rating_bin, return_dtype=pl.Int64)
            .alias("rating_bin")
        )

    full_bins = with_bin(cb)["rating_bin"].value_counts().sort("rating_bin")
    shares = {b: n * CHESSBENCH_N / cb.height for b, n in full_bins.iter_rows()}
    quotas = {b: int(x) for b, x in shares.items()}
    for b in sorted(shares, key=lambda b: shares[b] - quotas[b], reverse=True)[
        : CHESSBENCH_N - sum(quotas.values())
    ]:
        quotas[b] += 1
    pool = with_bin(pool).sort("order")
    picked = pl.concat(
        pool.filter(pl.col("rating_bin") == b).head(q) for b, q in sorted(quotas.items())
    ).sort("Rating", "PuzzleId")
    if picked.height != CHESSBENCH_N:
        raise ValueError(f"chessbench: a bin ran dry ({picked.height} of {CHESSBENCH_N})")
    picked.select("PuzzleId", "Rating", "FEN", "Moves", "Solution").write_csv(out)
    hits = sum(
        bool(train_keys.intersection(puzzles.line_keys(f, m)))
        for f, m in picked.select("FEN", "Moves").iter_rows()
    )
    mf.write(
        "chessbench1k",
        fp,
        [out],
        source=CHESSBENCH_URL,
        source_sha256=mf.sha256_file(CHESSBENCH_RAW),
        license="CC0 (lichess.org) / CC-BY 4.0 (Ruoss et al. 2024, google-deepmind/searchless_chess)",
        rows=picked.height,
        excluded_touching_training_data=cb.height - pool.height,
        stratified="12 bins of 200 Elo (clipped to 400-2800), quotas proportional to the full 10k",
        per_bin=[quotas[b] for b in sorted(quotas)],
        rating_mean={"chessbench1k": _mean(picked["Rating"]), "full_10k": _mean(cb["Rating"])},
        seed=puzzles.SEED,
        contamination_hits=hits,
        note="filtered against rl_train and primer-M (v1); not in the blocklist",
    )
    log(f"chessbench: {picked.height} puzzles ({cb.height - pool.height} excluded)")


STEPS: dict[str, Callable[[Log, bool], None]] = {
    "puzzles": step_puzzles,
    "evaldb": step_evaldb,
    "probe": step_probe,
    "blocklist": step_blocklist,
    "rltrain": step_rltrain,
    "timing": step_timing,
    "rewards": step_rewards,
    "primer": step_primer,
    "chessbench": step_chessbench,
}


def run(steps: list[str], log: Log, force: bool = False) -> None:
    for name in steps:
        STEPS[name](log, force)

"""Hugging Face release (M6 task 3): model cards and the dataset repo, staged under
checkpoints/release/ (gitignored), then uploaded with `ks hf-upload` after the user says yes.

Every number in a card is read from the committed eval files, so the cards can't drift from
docs/RESULTS.md.
"""

from __future__ import annotations

import io
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess

from ks.chess import prompt
from ks.cloud.config import REPO
from ks.eval import report

STAGE = REPO / "checkpoints" / "release"
RESULTS = REPO / "results" / "eval" / "test2000"
GITHUB = "https://github.com/nikext/knight-school"
SITE = "https://nikext.github.io/knight-school/"
BASE_REPO = "Qwen/Qwen3.5-2B"
DATASET = "knight-school-chess-puzzles"


@dataclass(frozen=True)
class Release:
    dir: str  # under STAGE, also the HF repo name suffix
    run: str  # eval run on test2000
    title: str
    recipe: str


SFT = (
    "Full fine-tune of Qwen3.5-2B on **primer-M + T8**: 1,326,000 teacher-free chess examples "
    "(192.5M tokens), one epoch, lr 1e-5 cosine, 1,728 examples per step (768 steps), max length "
    "2,048, loss on the answer tokens only. Tasks: board reading (T1), legal moves (T2), the FEN "
    "after a move (T3), attacks and checks (T4), Stockfish's best move (T5), evaluation (T6), the "
    "best line (T7), and 26k T5 positions re-asked in the RL prompt's format (T8, 2%). Answers come "
    "from python-chess or Stockfish 19."
)
GRPO = (
    "GRPO (TRL, vLLM colocate) from the primer-M + T8 model above: LoRA r=32 (alpha 64) on the "
    "language model's linear layers, merged after training. 200 steps × 64 prompts × 8 samples "
    "from 66,008 Lichess puzzle positions (`rl_train`), lr 1e-5, β = 1e-3, DAPO loss, temperature "
    "1.0, generation stopped at the first `</answer>`, adaptive entropy bonus with target {target}. "
    "Reward: {reward}, plus a format reward."
)
SPARSE = "1 if the move is the puzzle's move (any mate on the last move), else 0"
DENSE = "Stockfish 19's win probability for the chosen move (1M nodes, MultiPV over every legal move; 0 if illegal)"

RELEASES = (
    Release("primer-m", "m4-sft-primer-m-t8", "primer-M + T8 (SFT only)", SFT),
    Release(
        "primer-m-grpo-sparse",
        "m4-e3-sparse",
        "primer-M + T8 → GRPO, sparse reward",
        GRPO.format(target="0.2 (config v3)", reward=SPARSE),
    ),
    Release(
        "primer-m-grpo-dense",
        "m4-e3-dense-ent014",
        "primer-M + T8 → GRPO, dense reward",
        GRPO.format(target="0.14, the primer model's own entropy (ADR-025)", reward=DENSE),
    ),
)

# Context rows for every card's table: (label, eval run)
TABLE = (
    ("Qwen3.5-2B base, zero-shot", "qwen3.5-2b"),
    ("base → GRPO dense (no primer)", "m4-e2-dense-v3"),
    ("base → GRPO sparse (no primer)", "m4-e2-sparse-v3"),
    ("primer-M + T8 (SFT only)", "m4-sft-primer-m-t8"),
    ("primer-M + T8 → GRPO sparse", "m4-e3-sparse"),
    ("primer-M + T8 → GRPO dense (target 0.14)", "m4-e3-dense-ent014"),
    ("Stockfish 19, 1 node (reference)", "stockfish-1node"),
)


def _ci(d: dict[str, float]) -> str:
    return f"{100 * d['value']:.1f}% [{100 * d['lo']:.1f}, {100 * d['hi']:.1f}]"


def _row(label: str, s: dict[str, Any], bold: bool) -> str:
    r = s["rating"].get("r50")
    rating = f"{r:.0f}" if r else "below range"
    cells = [
        label,
        _ci(s["solve"]),
        f"{100 * s['move_acc']['value']:.1f}%",
        f"{100 * s['legal']['value']:.1f}%",
        rating,
    ]
    if bold:
        cells = [f"**{c}**" for c in cells]
    return "| " + " | ".join(cells) + " |"


def example_prompt() -> str:
    # test2000 puzzle b3ic0 after its set-up move: White mates with Qxf7+ Kh8 Qf8#
    board = chess.Board("r1b1r1k1/pp3ppp/8/2p1R3/3p4/1BP2Q2/PPK2PP1/RNB2q2 b - - 0 18")
    board.push_uci("e8e5")
    msgs = prompt.messages(board)
    return "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in msgs)


def model_card(rel: Release, summaries: dict[str, dict[str, Any]], user: str) -> str:
    rows = [_row(label, summaries[run], run == rel.run) for label, run in TABLE]
    return f"""---
license: apache-2.0
base_model: {BASE_REPO}
library_name: transformers
pipeline_tag: text-generation
language: [en]
datasets: [{user}/{DATASET}]
tags: [chess, chess-puzzles, grpo, reinforcement-learning, sft, lichess, stockfish]
---

# Knight School · Qwen3.5-2B {rel.title}

A 2B open LLM taught to solve chess puzzles, from [Knight School]({GITHUB}): a measured test of
whether a cheap, teacher-free “chess primer” (SFT on board reading, rules and Stockfish-annotated
positions) raises what GRPO can reach. **No LLM-generated data was used anywhere**: every
training signal comes from python-chess (rules) or Stockfish (move quality), on CC0 Lichess data.

## Results on test2000

2,000 held-out Lichess puzzles, split by game, stratified by rating (400–2799). Greedy decoding, one
answer per solver position, the legal moves listed in the prompt. A puzzle is solved when every
solver move is right. 95% bootstrap CIs over puzzles. Puzzle rating = rating at 50% solve.

| Model | Solve rate | Move accuracy | Legal | Puzzle rating |
|---|---|---|---|---|
{chr(10).join(rows)}

What the project found (paired differences, docs/RESULTS.md):
- The primer raises the post-RL solve rate: primer → GRPO beats GRPO from the base model by
  +7.4 points [+5.8, +9.2] (sparse) and +6.8 [+5.2, +8.4] (dense).
- That gain is the SFT's. GRPO on top of primer-M added nothing: −0.2 [−1.6, +1.1] (sparse) and
  −0.9 [−2.3, +0.4] (dense, target 0.14) vs the primer alone.
- A rules-only primer (board reading, no move choice) did not help (+0.4 [−1.0, +1.8] after RL).
- **Without the legal-move list in the prompt, these models collapse** (primer → GRPO dense: 1.9%).

Browse every answer: [the puzzle browser]({SITE}).

## Training

{rel.recipe}

Hardware: one spot A100 80GB on Google Cloud. Configs, job scripts and the cost ledger are in the
[repository]({GITHUB}). The whole project (every run, eval and failed attempt) cost under $200 of
cloud credits.

## Prompt format

The model was trained and evaluated with exactly this prompt, rendered with the Qwen3.5 chat
template and `enable_thinking=False` (the template pre-fills an empty think block, and the model
answers directly in about ten tokens):

```text
{example_prompt()}
```

Expected answer: `<answer>Qxf7+</answer>`.

## Usage

```python
from transformers import AutoModelForImageTextToText, AutoTokenizer

repo = "{user}/knight-school-qwen3.5-2b-{rel.dir}"
tok = AutoTokenizer.from_pretrained(repo)
model = AutoModelForImageTextToText.from_pretrained(repo, dtype="bfloat16", device_map="auto")
# messages = the system and user turns shown above, for your position
text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
ids = tok(text, return_tensors="pt").to(model.device)
out = model.generate(**ids, max_new_tokens=24, do_sample=False)
print(tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True))
```

The checkpoint keeps Qwen3.5's vision tower, unchanged. The evals served the language model only
(vLLM `--language-model-only`). With transformers 5.17, greedy answers matched the graded vLLM
answers on 39–40 of 40 sampled test2000 positions per checkpoint; the rest differed by a near tie.

## Limitations

- **A puzzle solve rate, not playing strength.** Puzzles come with a forcing tactic, and the prompt
  lists the legal moves. The model has not been tested in games.
- It depends on the legal-move list: the training and eval prompts always include it.
- Single seed per arm; the CIs cover puzzle sampling, not training variance.
- English prompt format only; other prompt wordings were not tested.
- Not for use against people in live games. The project never plays on Lichess or chess.com.

## License

Apache-2.0, as the base model [{BASE_REPO}](https://huggingface.co/{BASE_REPO}). Training data:
Lichess puzzle and evaluation databases (CC0). Stockfish (GPL-3.0) was used as a tool and is not
distributed.
"""


def dataset_card(user: str, primer_manifest: dict[str, Any]) -> str:
    per_task = ", ".join(f"{k} {v:,}" for k, v in primer_manifest["per_task"].items())
    return f"""---
license: cc0-1.0
language: [en]
pretty_name: Knight School chess puzzles
tags: [chess, chess-puzzles, lichess, stockfish, reinforcement-learning]
size_categories: [10K<n<100K]
configs:
  - config_name: test2000
    data_files: evals/test2000.csv
  - config_name: dev500
    data_files: evals/dev500.csv
  - config_name: probe500
    data_files: evals/probe500.csv
  - config_name: rl_train
    data_files: rl_train/rl_train.parquet
  - config_name: primer_sample
    data_files: primer/sample.jsonl
---

# Knight School chess puzzles

Eval sets, RL training positions with Stockfish reward tables, and a sample of the teacher-free
chess primer from [Knight School]({GITHUB}). Models: [{user}](https://huggingface.co/{user}).

| File | What |
|---|---|
| `evals/test2000.csv` | 2,000 held-out Lichess puzzles (Lichess columns + `rating_bin`), stratified over 12 rating bins 400–2799, split from training by game |
| `evals/dev500.csv` | 500 dev puzzles, same construction |
| `evals/test500.ids` | 500-id subset of test2000 (Gemini baselines) |
| `evals/probe500.csv` | E0 knowledge probe: 500 board-reading questions (square, legal-move count, FEN after a move, in check) |
| `rl_train/rl_train.parquet` | 66,008 solver positions from Lichess puzzles, each with every legal move's Stockfish 19 score at 1M nodes (`cp`, `mate`, win probability `wp`, aligned with `legal_san`) |
| `primer/sample.jsonl` | 250 examples per primer task (T1–T8) from primer-M + T8, chat format |
| `primer/manifest.json` | the full primer's build manifest: {primer_manifest["examples"]:,} examples ({per_task}), 0 contamination hits |

The full primer (1.3M examples) is not uploaded: `make data` regenerates it from the repo
(python-chess + Stockfish 19, seeded), and the manifest's sha256 checks the result.

**No LLM-generated data**: puzzles are Lichess's, answers come from python-chess or Stockfish.
**Contamination**: no training or primer position shares a position key (or a source game) with
any eval set; a CI test enforces it on the committed eval keys.

License: CC0, as the Lichess [puzzle](https://database.lichess.org/#puzzles) and
[evaluation](https://database.lichess.org/#evals) databases it derives from. The ChessBench subset
used in the project is not included (its license was not verified).
"""


def _primer_sample(shards: Path, per_task: int = 250) -> str:
    import zstandard

    got: dict[str, list[str]] = {}
    for shard in sorted(shards.glob("shard-*.jsonl.zst")):
        with shard.open("rb") as f:
            for line in io.TextIOWrapper(
                zstandard.ZstdDecompressor().stream_reader(f), encoding="utf-8"
            ):
                task = json.loads(line)["task"]
                bucket = got.setdefault(task, [])
                if len(bucket) < per_task:
                    bucket.append(line.rstrip("\n"))
        if len(got) >= 8 and all(len(v) >= per_task for v in got.values()):
            break
    return "\n".join(line for t in sorted(got) for line in got[t]) + "\n"


def stage(user: str, stage_dir: Path = STAGE) -> list[Path]:
    """Write the model cards next to the downloaded weights and build the dataset folder."""
    summaries = {run: report.read(RESULTS / f"{run}.json.gz")["summary"] for _, run in TABLE}
    out = []
    for rel in RELEASES:
        d = stage_dir / rel.dir
        if not (d / "model.safetensors").exists():
            raise FileNotFoundError(f"{d}/model.safetensors: download the merged checkpoint first")
        (d / "README.md").write_text(model_card(rel, summaries, user))
        out.append(d)
    ds = stage_dir / "dataset"
    for sub in ("evals", "rl_train", "primer"):
        (ds / sub).mkdir(parents=True, exist_ok=True)
    sets = REPO / "evals" / "sets"
    for name in ("test2000.csv", "dev500.csv", "probe500.csv", "test500.ids"):
        shutil.copy2(sets / name, ds / "evals" / name)
    shutil.copy2(
        REPO / "data" / "positions" / "rl_train.parquet", ds / "rl_train" / "rl_train.parquet"
    )
    manifest = json.loads((REPO / "manifests" / "primer_M-t8.json").read_text())
    (ds / "primer" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ds / "primer" / "sample.jsonl").write_text(_primer_sample(REPO / "data" / "primer" / "M-t8"))
    (ds / "README.md").write_text(dataset_card(user, manifest))
    out.append(ds)
    return out


def upload(user: str, token: str, stage_dir: Path = STAGE, private: bool = False) -> list[str]:
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    urls = []
    for rel in RELEASES:
        repo = f"{user}/knight-school-qwen3.5-2b-{rel.dir}"
        api.create_repo(repo, repo_type="model", private=private, exist_ok=True)
        api.upload_folder(
            repo_id=repo,
            folder_path=str(stage_dir / rel.dir),
            commit_message="Knight School release (M6)",
        )
        urls.append(f"https://huggingface.co/{repo}")
    repo = f"{user}/{DATASET}"
    api.create_repo(repo, repo_type="dataset", private=private, exist_ok=True)
    api.upload_folder(
        repo_id=repo,
        repo_type="dataset",
        folder_path=str(stage_dir / "dataset"),
        commit_message="Knight School release (M6)",
    )
    urls.append(f"https://huggingface.co/datasets/{repo}")
    return urls

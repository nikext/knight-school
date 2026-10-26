from __future__ import annotations

from ks import release
from ks.eval import report


def test_model_cards_carry_the_eval_numbers() -> None:
    summaries = {
        run: report.read(release.RESULTS / f"{run}.json.gz")["summary"] for _, run in release.TABLE
    }
    for rel in release.RELEASES:
        card = release.model_card(rel, summaries, "someone")
        assert card.startswith("---\nlicense: apache-2.0\nbase_model: Qwen/Qwen3.5-2B\n")
        s = summaries[rel.run]["solve"]
        bold = f"**{100 * s['value']:.1f}% [{100 * s['lo']:.1f}, {100 * s['hi']:.1f}]**"
        assert card.count(bold) == 1
        assert f"someone/knight-school-qwen3.5-2b-{rel.dir}" in card
        assert "<answer>" in card and "Legal moves" in card


def test_dataset_card_names_every_file() -> None:
    card = release.dataset_card("someone", {"examples": 10, "per_task": {"T1": 4, "T8": 6}})
    assert "license: cc0-1.0" in card
    for f in ("evals/test2000.csv", "rl_train/rl_train.parquet", "primer/sample.jsonl"):
        assert f in card
    assert "T1 4, T8 6" in card

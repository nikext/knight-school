"""Trimming right padding per chunk gives TRL's exact log-probs and entropies (local only)."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
trl = pytest.importorskip("trl")
transformers = pytest.importorskip("transformers")

from ks.train.trim import trimmed  # noqa: E402


def stub(cls):
    t = object.__new__(cls)  # no Trainer.__init__: the method only needs accelerator.autocast
    t.accelerator = SimpleNamespace(autocast=contextlib.nullcontext, is_main_process=False)
    t.args = SimpleNamespace(report_to=[])
    return t


def test_trimmed_matches_trl_on_ragged_padding():
    torch.manual_seed(0)
    cfg = transformers.LlamaConfig(
        vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
        num_attention_heads=4, num_key_value_heads=4, max_position_embeddings=64,
    )  # fmt: skip
    model = transformers.LlamaForCausalLM(cfg).eval()
    trl.trainer.utils.add_fused_lm_head(
        model, outputs=("log_probs", "entropy")
    )  # as GRPOTrainer does
    b, prompt, comp = 6, 5, 12
    ids = torch.randint(1, 64, (b, prompt + comp))
    mask = torch.ones_like(ids)
    lengths = [12, 2, 3, 1, 4, 2]  # one long completion; chunk 2 (rows 2-3) needs only 3 columns
    for i, n in enumerate(lengths):
        mask[i, prompt + n :] = 0
        ids[i, prompt + n :] = 0
    mask[1, :2] = 0  # a left-padded prompt
    base = trl.GRPOTrainer
    Trim = trimmed(base)
    with torch.no_grad():
        ref = base._get_per_token_logps_and_entropies(stub(Trim), model, ids, mask, comp, 2, True)
        got = Trim._get_per_token_logps_and_entropies(stub(Trim), model, ids, mask, comp, 2, True)
    cmask = mask[:, -comp:].bool()
    assert got[0].shape == ref[0].shape == (b, comp)
    assert torch.allclose(got[0][cmask], ref[0][cmask], atol=1e-5)
    assert torch.allclose(got[1][cmask], ref[1][cmask], atol=1e-5)
    t = stub(Trim)
    Trim._get_per_token_logps_and_entropies(t, model, ids, mask, comp, 2, False)
    # sorted by completion length: (12, 4) | (3, 2) | (2, 1) -> chunks need 12, 3, 2 columns
    assert t.trimmed_columns == 2 * (12 - 3) + 2 * (12 - 2) and t.total_columns == b * comp


def test_sort_by_length_permutes_every_field_in_unison():
    from ks.train.trim import sort_by_length

    cm = torch.tensor([[1, 0, 0], [1, 1, 1], [1, 1, 0]])
    out = sort_by_length(
        {
            "completion_mask": cm,
            "adv": torch.tensor([0.0, 1.0, 2.0]),
            "id": ["a", "b", "c"],
            "n": torch.tensor(5),
            "x": None,
        }
    )
    assert out["completion_mask"].sum(-1).tolist() == [3, 2, 1]
    assert out["adv"].tolist() == [1.0, 2.0, 0.0] and out["id"] == ["b", "c", "a"]
    assert int(out["n"]) == 5 and out["x"] is None

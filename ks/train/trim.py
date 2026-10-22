"""Per-chunk trimming of right padding in TRL's log-prob passes (M3, ADR-019).

TRL 1.16 pads every completion in a generation batch to the longest one. In the M3 smoke,
0.8% of 512 completions still hit the 1024-token cap at step 13, when the mean length was 18,
so every forward and backward ran 1,245 columns and a step took ~127 s on an A100
regardless of the mean length.

Completions are right-padded, so the columns after a chunk's last real token are padding in
every row. Dropping them before the forward pass and padding the outputs back with zeros
gives the same log-probs and entropies at every real position (the model is causal), and the
padded positions are masked out of the loss either way. Every log-prob pass goes through
`_get_per_token_logps_and_entropies` (policy, reference, old policy), so trimming there
covers them all.

Trimming alone left a step at ~62 s once completions were ~20 tokens (m3-tput-a100): a few
clipped completions, spread at random over 64 micro-batches, kept many of them at full width.
So the rows are also ordered by length, which puts the long ones together:
- a multi-chunk pass (the reference model's) sorts its rows, runs the chunks, and puts the
  results back in the original order;
- the step's micro-batches are cut from the generation batch sorted by completion length
  (`sort_by_length`, in place of TRL's random shuffle). With `loss_type: dapo` every
  micro-batch's loss is its token sum over the whole generation batch's token count, so
  the accumulated gradient doesn't depend on how rows are grouped.
"""

from __future__ import annotations

from typing import Any


def sort_by_length(seq_dict: dict[str, Any]) -> dict[str, Any]:
    """TRL's `shuffle_sequence_dict` contract, but ordered by completion length (longest first)."""
    import torch

    lengths = seq_dict["completion_mask"].sum(dim=-1)
    order = torch.argsort(lengths, descending=True, stable=True).tolist()

    def permute(v: Any) -> Any:
        if v is None or (isinstance(v, torch.Tensor) and v.ndim == 0):
            return v
        if isinstance(v, torch.Tensor):
            return v[order]
        return [v[i] for i in order]

    return {k: permute(v) for k, v in seq_dict.items()}


def install_sorted_batches() -> None:
    """Make GRPOTrainer cut its micro-batches from the length-sorted generation batch."""
    from trl.trainer import grpo_trainer  # type: ignore[import-not-found]

    setattr(grpo_trainer, "shuffle_sequence_dict", sort_by_length)  # noqa: B010


def trimmed(trainer_cls: type) -> type:
    """A subclass of a TRL GRPOTrainer class whose text-only log-prob passes trim each chunk."""
    import torch
    import torch.nn.functional as F

    class Trimmed(trainer_cls):  # type: ignore[valid-type, misc]
        trimmed_columns = 0  # columns skipped since the last read (for the step log)
        total_columns = 0

        def _get_per_token_logps_and_entropies(  # type: ignore[override]
            self,
            model: Any,
            input_ids: Any,
            attention_mask: Any,
            logits_to_keep: int,
            batch_size: int | None = None,
            compute_entropy: bool = False,
            compute_aux_loss: bool = False,
            **multimodal: Any,
        ) -> tuple[Any, Any, Any]:
            parent = super()._get_per_token_logps_and_entropies
            if any(v is not None for v in multimodal.values()):
                return parent(
                    model, input_ids, attention_mask, logits_to_keep, batch_size,
                    compute_entropy, compute_aux_loss, **multimodal,
                )  # fmt: skip
            bs = batch_size or input_ids.size(0)
            width = input_ids.size(1)
            order = None
            if bs < input_ids.size(0):  # several chunks: group rows of similar length
                comp_len = attention_mask[:, -logits_to_keep:].sum(dim=-1)
                order = torch.argsort(comp_len, descending=True, stable=True)
                input_ids, attention_mask = input_ids[order], attention_mask[order]
            logps, ents, auxes = [], [], []
            for start in range(0, input_ids.size(0), bs):
                ids, am = input_ids[start : start + bs], attention_mask[start : start + bs]
                used = int(am.any(dim=0).nonzero().max()) + 1  # last column with a real token
                cut = min(width - used, logits_to_keep - 1)  # score at least one column
                keep = logits_to_keep - cut
                lp, en, aux = parent(
                    model, ids[:, : width - cut], am[:, : width - cut], keep, None,
                    compute_entropy, compute_aux_loss,
                )  # fmt: skip
                logps.append(F.pad(lp, (0, cut)))
                if en is not None:
                    ents.append(F.pad(en, (0, cut)))
                if aux is not None:
                    auxes.append(aux)
                self.trimmed_columns += cut * ids.size(0)
                self.total_columns += logits_to_keep * ids.size(0)
            lp_all = torch.cat(logps, dim=0)
            en_all = torch.cat(ents, dim=0) if ents else None
            if order is not None:
                back = torch.argsort(order)
                lp_all = lp_all[back]
                en_all = en_all[back] if en_all is not None else None
            return lp_all, en_all, torch.stack(auxes).mean() if auxes else None

    Trimmed.__name__ = f"Trimmed{trainer_cls.__name__}"
    return Trimmed

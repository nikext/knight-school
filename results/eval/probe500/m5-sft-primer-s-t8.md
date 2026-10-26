# m5-sft-primer-s-t8 on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `7190e0411a2e`; 2026-10-26T06:28:10Z, 4 s, cost $0.0457
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 55.2% [46.4, 64.0] |
| P2 legal count | 125 | 6.4% [2.4, 11.2] |
| P3 FEN after move | 125 | 12.0% [6.4, 17.6] |
| P4 in check | 125 | 57.6% [48.8, 66.4] |

P2 legal-move list F1: 28.8% [25.3, 32.3]

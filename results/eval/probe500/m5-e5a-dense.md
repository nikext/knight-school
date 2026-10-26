# m5-e5a-dense on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `7190e0411a2e`; 2026-10-26T05:15:33Z, 4 s, cost $0.0468
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 99.2% [97.6, 100.0] |
| P2 legal count | 125 | 9.6% [4.8, 15.2] |
| P3 FEN after move | 125 | 95.2% [91.2, 98.4] |
| P4 in check | 125 | 88.0% [81.6, 93.6] |

P2 legal-move list F1: 69.9% [63.9, 75.6]

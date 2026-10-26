# m5-sft-rules-m-t9-10 on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `7190e0411a2e`; 2026-10-26T02:13:19Z, 4 s, cost $0.0459
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 99.2% [97.6, 100.0] |
| P2 legal count | 125 | 11.2% [6.4, 16.8] |
| P3 FEN after move | 125 | 94.4% [90.4, 98.4] |
| P4 in check | 125 | 88.8% [83.2, 93.6] |

P2 legal-move list F1: 70.4% [64.6, 76.1]

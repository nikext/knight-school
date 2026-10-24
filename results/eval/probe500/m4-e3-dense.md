# m4-e3-dense on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `1a92ddf79865`; 2026-10-24T02:26:14Z, 4 s, cost $0.0468
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 97.6% [94.4, 100.0] |
| P2 legal count | 125 | 7.2% [3.2, 12.0] |
| P3 FEN after move | 125 | 91.2% [85.6, 96.0] |
| P4 in check | 125 | 80.0% [72.8, 86.4] |

P2 legal-move list F1: 70.9% [65.1, 76.6]

# m3-e2-dense on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `25b5dd417d43`; 2026-10-22T18:39:35Z, 39 s, cost $0.0351
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 1.6% [0.0, 4.0] |
| P2 legal count | 125 | 3.2% [0.8, 6.4] |
| P3 FEN after move | 125 | 0.0% [0.0, 0.0] |
| P4 in check | 125 | 50.4% [41.6, 59.2] |

P2 legal-move list F1: 3.5% [2.4, 4.6]

# qwen3.5-2b on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `90bfc56fc862`; 2026-10-22T07:47:57Z, 12 s, cost $0.0496
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 4.8% [1.6, 8.8] |
| P2 legal count | 125 | 4.0% [0.8, 8.0] |
| P3 FEN after move | 125 | 0.0% [0.0, 0.0] |
| P4 in check | 125 | 50.4% [41.6, 59.2] |

P2 legal-move list F1: 2.4% [1.7, 3.2]

# qwen3-1.7b on probe500 (E0)

- model: `Qwen/Qwen3-1.7B`
- git `90bfc56fc862`; 2026-10-22T07:49:00Z, 5 s, cost $0.0291
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 11.2% [5.6, 16.8] |
| P2 legal count | 125 | 2.4% [0.0, 5.6] |
| P3 FEN after move | 125 | 0.0% [0.0, 0.0] |
| P4 in check | 125 | 50.4% [41.6, 59.2] |

P2 legal-move list F1: 2.9% [2.3, 3.7]

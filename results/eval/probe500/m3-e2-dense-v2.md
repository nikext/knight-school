# m3-e2-dense-v2 on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `35e9bf043759`; 2026-10-22T22:13:40Z, 10 s, cost $0.0504
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 3.2% [0.8, 6.4] |
| P2 legal count | 125 | 4.0% [0.8, 8.0] |
| P3 FEN after move | 125 | 0.0% [0.0, 0.0] |
| P4 in check | 125 | 50.4% [41.6, 59.2] |

P2 legal-move list F1: 2.8% [1.9, 3.8]

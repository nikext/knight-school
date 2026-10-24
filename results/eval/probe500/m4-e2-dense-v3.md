# m4-e2-dense-v3 on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `91af7e44bf9f`; 2026-10-23T12:25:46Z, 8 s, cost $0.0519
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 1.6% [0.0, 4.0] |
| P2 legal count | 125 | 4.0% [0.8, 8.0] |
| P3 FEN after move | 125 | 0.0% [0.0, 0.0] |
| P4 in check | 125 | 50.4% [41.6, 59.2] |

P2 legal-move list F1: 0.7% [0.3, 1.2]

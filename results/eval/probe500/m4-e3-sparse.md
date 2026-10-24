# m4-e3-sparse on probe500 (E0)

- model: `Qwen/Qwen3.5-2B`
- git `1a92ddf79865`; 2026-10-24T23:50:21Z, 11 s, cost $0.0346
- decoding: T=0.0, max 1024 tokens, chat template {'enable_thinking': False}

| Task | n | exact match |
|---|---|---|
| P1 square | 125 | 98.4% [96.0, 100.0] |
| P2 legal count | 125 | 12.8% [7.2, 19.2] |
| P3 FEN after move | 125 | 90.4% [84.8, 95.2] |
| P4 in check | 125 | 80.0% [72.8, 86.4] |

P2 legal-move list F1: 65.8% [59.7, 71.8]

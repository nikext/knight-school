import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { binRates, MODEL_COLOR, pct } from "../lib";
import type { Dataset } from "../types";

const DOCS = "https://github.com/nikext/knight-school/blob/main/docs/RESULTS.md";

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/** Paired differences on test2000 (docs/RESULTS.md), points with 95% bootstrap CIs. */
const FINDINGS = [
  {
    big: "+7.4",
    unit: "points",
    ci: "[+5.8, +9.2]",
    title: "The primer raises the RL result",
    text: "Primer → RL vs Base → RL, same sparse reward and config. H1 holds, with dense reward too (+6.8).",
  },
  {
    big: "−0.2",
    unit: "points",
    ci: "[−1.6, +1.1]",
    title: "…but RL adds nothing to the primer",
    text: "Primer → RL vs the primer alone. The gain is the SFT's. On the 10× smaller primer-S, RL did add +4.0 (dense reward).",
  },
  {
    big: "+0.4",
    unit: "points",
    ci: "[−1.0, +1.8]",
    title: "Rules alone don't help",
    text: "A rules-only primer (board reading, legal moves, no move choice) → RL, vs RL from the base model (both dense). The move-choice data is what matters.",
  },
  {
    big: "1.9%",
    unit: "solved",
    ci: "",
    title: "Remove the legal-move list and it collapses",
    text: "Every model sees the legal moves in its prompt. Without them, primer → RL solves 1.9%. The skill measured is picking the tactic from a list.",
  },
];

export default function Results({ data }: { data: Dataset }) {
  const { n, rates } = useMemo(() => binRates(data), [data]);
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);

  const H = 320;
  const m = { l: 44, r: 12, t: 12, b: 44 };
  const W = Math.max(width, 280);
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  const x = (b: number) => m.l + (iw * (b + 0.5)) / data.bins.length;
  const y = (v: number) => m.t + ih * (1 - v);
  const narrow = W < 520;

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const b = Math.floor(((e.clientX - r.left) / r.width) * data.bins.length);
    setHover(Math.max(0, Math.min(data.bins.length - 1, b)));
  };

  // models drawn so the hero series (primer → RL) sits on top
  const order = [...data.models.keys()].sort((a, b) => (data.models[a].key === "primer_rl" ? 1 : 0) - (data.models[b].key === "primer_rl" ? 1 : 0));

  return (
    <main className="page">
      <header className="page-head">
        <h1>Results on 2,000 held-out puzzles</h1>
        <p className="lede">
          Qwen3.5-2B, one greedy answer per position, with the legal moves listed in the prompt. A puzzle counts as solved only if every one of
          the solver's moves is right. 95% bootstrap confidence intervals. The full write-up, with predictions made before each run, is in{" "}
          <a href={DOCS} target="_blank" rel="noreferrer">
            RESULTS.md
          </a>
          .
        </p>
      </header>

      <section className="tiles" aria-label="Solve rate per model">
        {data.models.map((mdl) => (
          <div key={mdl.key} className={`tile${mdl.key === "primer_rl" ? " hero" : ""}`}>
            <div className="tile-label">
              <span className="swatch" style={{ background: MODEL_COLOR[mdl.key] }} />
              {mdl.label}
            </div>
            <div className="tile-num">{pct(mdl.solve.value)}</div>
            <div className="tile-ci">
              [{pct(mdl.solve.lo)}, {pct(mdl.solve.hi)}] solved
            </div>
            <div className="tile-sub">{mdl.blurb}</div>
          </div>
        ))}
      </section>

      <section className="card chart-card">
        <div className="chart-head">
          <div>
            <h2>Solve rate by puzzle rating</h2>
            <p className="muted small">~167 puzzles per bin. Stockfish at 1 node is a strong reference, not a weak one.</p>
          </div>
          <div className="segmented small" role="tablist" aria-label="Chart or table">
            <button role="tab" aria-selected={!table} className={!table ? "on" : ""} onClick={() => setTable(false)}>
              Chart
            </button>
            <button role="tab" aria-selected={table} className={table ? "on" : ""} onClick={() => setTable(true)}>
              Table
            </button>
          </div>
        </div>
        <ul className="legend" aria-label="Legend">
          {data.models.map((mdl) => (
            <li key={mdl.key}>
              <svg width="18" height="10" aria-hidden="true">
                <line x1="1" y1="5" x2="17" y2="5" stroke={MODEL_COLOR[mdl.key]} strokeWidth="2.5" strokeDasharray={mdl.key === "stockfish" ? "4 3" : undefined} strokeLinecap="round" />
              </svg>
              {mdl.label}
            </li>
          ))}
        </ul>

        {table ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Rating</th>
                  <th scope="col">n</th>
                  {data.models.map((mdl) => (
                    <th scope="col" key={mdl.key}>
                      {mdl.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.bins.map((b, i) => (
                  <tr key={b}>
                    <th scope="row">{b}</th>
                    <td>{n[i]}</td>
                    {data.models.map((mdl, j) => (
                      <td key={mdl.key}>{pct(rates[j][i])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="chart" ref={ref}>
            <svg width={W} height={H} role="img" aria-label="Line chart of solve rate per rating bin for each model">
              {[0, 0.25, 0.5, 0.75, 1].map((v) => (
                <g key={v}>
                  <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} className={v === 0 ? "axis" : "grid"} />
                  <text x={m.l - 8} y={y(v)} className="tick" textAnchor="end" dominantBaseline="middle">
                    {v * 100}%
                  </text>
                </g>
              ))}
              {data.bins.map((b, i) =>
                !narrow || i % 2 === 0 ? (
                  <text key={b} x={x(i)} y={H - m.b + 18} className="tick" textAnchor="middle">
                    {b.split("-")[0]}
                  </text>
                ) : null,
              )}
              <text x={m.l + iw / 2} y={H - 6} className="tick" textAnchor="middle">
                Puzzle rating (bin start)
              </text>
              {hover != null && <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={m.t + ih} className="crosshair" />}
              {order.map((j) => {
                const mdl = data.models[j];
                const d = rates[j].map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join("");
                return (
                  <g key={mdl.key}>
                    <path d={d} fill="none" stroke={MODEL_COLOR[mdl.key]} strokeWidth={mdl.key === "primer_rl" ? 2.5 : 2} strokeDasharray={mdl.key === "stockfish" ? "5 4" : undefined} strokeLinejoin="round" strokeLinecap="round" />
                    {hover != null && <circle cx={x(hover)} cy={y(rates[j][hover])} r={4.5} fill={MODEL_COLOR[mdl.key]} className="marker" />}
                  </g>
                );
              })}
              <rect
                x={m.l}
                y={m.t}
                width={iw}
                height={ih}
                fill="transparent"
                onPointerMove={onMove}
                onPointerDown={onMove}
                onPointerLeave={() => setHover(null)}
              />
            </svg>
            {hover != null && (
              <div className="tooltip" style={{ left: Math.min(x(hover) + 12, W - 190), top: m.t + 4 }} role="status">
                <div className="tooltip-title">
                  Rating {data.bins[hover]} <span className="muted">· n={n[hover]}</span>
                </div>
                {order
                  .slice()
                  .reverse()
                  .sort((a, b) => rates[b][hover] - rates[a][hover])
                  .map((j) => (
                    <div key={j} className="tooltip-row">
                      <svg width="14" height="8" aria-hidden="true">
                        <line x1="1" y1="4" x2="13" y2="4" stroke={MODEL_COLOR[data.models[j].key]} strokeWidth="2.5" strokeLinecap="round" />
                      </svg>
                      <strong>{pct(rates[j][hover])}</strong>
                      <span className="muted">{data.models[j].label}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="findings" aria-label="Key comparisons">
        {FINDINGS.map((f) => (
          <article key={f.title} className="card finding">
            <div className="finding-num">
              {f.big} <span className="finding-unit">{f.unit}</span>
            </div>
            {f.ci && <div className="tile-ci">95% CI {f.ci}</div>}
            <h3>{f.title}</h3>
            <p>{f.text}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

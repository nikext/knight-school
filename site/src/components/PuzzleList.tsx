import { useEffect, useMemo, useRef } from "react";
import { defaultFilters, MODEL_COLOR, pct, PRESETS, RATING_MAX, RATING_MIN, solveRates, tacticsFirst, themeCounts, themeName } from "../lib";
import type { Dataset, Filters, Puzzle, Want } from "../types";
import { IconSearch } from "./Icons";

interface Props {
  data: Dataset;
  list: Puzzle[];
  filters: Filters;
  setFilters: (f: Filters) => void;
  currentId: string | null;
  onOpen: (id: string) => void;
}

const NEXT: Record<Want, Want> = { any: "yes", yes: "no", no: "any" };
const WANT_LABEL: Record<Want, string> = { any: "either", yes: "solved", no: "missed" };

export default function PuzzleList({ data, list, filters: f, setFilters, currentId, onOpen }: Props) {
  const themes = useMemo(() => themeCounts(data.puzzles).slice(0, 40), [data]);
  const rates = useMemo(() => solveRates(data, list), [data, list]);
  const listRef = useRef<HTMLOListElement>(null);
  const set = (patch: Partial<Filters>) => setFilters({ ...f, ...patch });
  const presetIndex = PRESETS.findIndex((p) => data.models.every((m) => (p.want[m.key] ?? "any") === f.want[m.key]));
  const dirty = JSON.stringify(f) !== JSON.stringify(defaultFilters(data.models.map((m) => m.key)));

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="true"]');
    el?.scrollIntoView({ block: "nearest" });
  }, [currentId]);

  return (
    <div className="plist">
      <div className="filters">
        <label className="search">
          <IconSearch />
          <input
            type="search"
            placeholder="Search id or theme"
            value={f.q}
            onChange={(e) => set({ q: e.target.value })}
            aria-label="Search puzzles by id or theme"
          />
        </label>

        <div className="field">
          <label htmlFor="preset" className="field-label">Outcome</label>
          <select
            id="preset"
            value={presetIndex}
            onChange={(e) => {
              const p = PRESETS[Number(e.target.value)];
              if (p) set({ want: Object.fromEntries(data.models.map((m) => [m.key, p.want[m.key] ?? "any"])) });
            }}
          >
            {presetIndex < 0 && <option value={-1}>Custom</option>}
            {PRESETS.map((p, i) => (
              <option key={p.label} value={i}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="want-chips" role="group" aria-label="Filter by each model's result">
          {data.models.map((m) => {
            const w = f.want[m.key] ?? "any";
            return (
              <button
                key={m.key}
                className={`want-chip want-${w}`}
                onClick={() => set({ want: { ...f.want, [m.key]: NEXT[w] } })}
                title={`${m.label}: ${WANT_LABEL[w]} (click to change)`}
                aria-label={`${m.label}: ${WANT_LABEL[w]}. Click to change.`}
              >
                <span className="swatch" style={{ background: MODEL_COLOR[m.key] }} />
                {m.label}
                <span className="want-mark" aria-hidden="true">
                  {w === "yes" ? "✓" : w === "no" ? "✗" : "·"}
                </span>
              </button>
            );
          })}
        </div>

        <p className="filter-help">Tap a model to show puzzles it solved ✓ or missed ✗.</p>

        <div className="field">
          <span className="field-label">
            Rating <span className="muted">{f.minR}–{f.maxR}</span>
          </span>
          <div className="range2">
            <input
              type="range"
              min={RATING_MIN}
              max={RATING_MAX}
              step={100}
              value={f.minR}
              aria-label="Minimum rating"
              onChange={(e) => set({ minR: Math.min(Number(e.target.value), f.maxR - 100) })}
            />
            <input
              type="range"
              min={RATING_MIN}
              max={RATING_MAX}
              step={100}
              value={f.maxR}
              aria-label="Maximum rating"
              onChange={(e) => set({ maxR: Math.max(Number(e.target.value), f.minR + 100) })}
            />
            <div
              className="range2-fill"
              style={{
                left: `${((f.minR - RATING_MIN) / (RATING_MAX - RATING_MIN)) * 100}%`,
                right: `${100 - ((f.maxR - RATING_MIN) / (RATING_MAX - RATING_MIN)) * 100}%`,
              }}
            />
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="theme" className="field-label">Theme</label>
            <select id="theme" value={f.theme} onChange={(e) => set({ theme: e.target.value })}>
              <option value="">Any theme</option>
              {themes.map(([t, n]) => (
                <option key={t} value={t}>
                  {themeName(t)} ({n})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sort" className="field-label">Sort</label>
            <select id="sort" value={f.sort} onChange={(e) => set({ sort: e.target.value as Filters["sort"] })}>
              <option value="rating">Rating ↑</option>
              <option value="-rating">Rating ↓</option>
              <option value="id">Id</option>
            </select>
          </div>
        </div>
      </div>

      <div className="selection">
        <div className="selection-head">
          <span>
            <strong>{list.length.toLocaleString()}</strong> {list.length === 1 ? "puzzle" : "puzzles"}
          </span>
          {dirty && (
            <button className="link-btn" onClick={() => setFilters(defaultFilters(data.models.map((m) => m.key)))}>
              Reset filters
            </button>
          )}
        </div>
        <ul className="mini-rates" aria-label="Solve rate in this selection">
          {data.models.map((m, j) => (
            <li key={m.key}>
              <span className="mini-label">{m.label}</span>
              <span className="mini-track">
                <span className="mini-bar" style={{ width: `${rates[j] * 100}%`, background: MODEL_COLOR[m.key] }} />
              </span>
              <span className="mini-val">{list.length ? pct(rates[j], 0) : "–"}</span>
            </li>
          ))}
        </ul>
      </div>

      <ol className="rows" ref={listRef} aria-label="Puzzles">
        {list.map((p) => (
          <li key={p.id}>
            <button className="row" aria-current={p.id === currentId} onClick={() => onOpen(p.id)}>
              <span className="row-rating">{p.r}</span>
              <span className="row-main">
                <span className="row-id">{p.id}</span>
                <span className="row-themes">{tacticsFirst(p.t).slice(0, 3).map(themeName).join(" · ")}</span>
              </span>
              <span className="row-dots" aria-label={data.models.map((m, j) => `${m.label} ${p.s[j] ? "solved" : "missed"}`).join(", ")}>
                {data.models.map((m, j) => (
                  <span
                    key={m.key}
                    className={`dot${p.s[j] ? " on" : ""}`}
                    style={{ ["--c" as string]: MODEL_COLOR[m.key] }}
                    title={`${m.label}: ${p.s[j] ? "solved" : "missed"}`}
                  />
                ))}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

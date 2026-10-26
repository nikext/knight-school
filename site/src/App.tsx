import { useCallback, useEffect, useMemo, useState } from "react";
import About from "./components/About";
import Header from "./components/Header";
import PuzzleList from "./components/PuzzleList";
import PuzzleView from "./components/PuzzleView";
import Results from "./components/Results";
import { IconClose } from "./components/Icons";
import { useMedia, usePersisted, useRoute } from "./hooks";
import { applyFilters, defaultFilters } from "./lib";
import type { Dataset, Filters } from "./types";

export type BoardTheme = "brown" | "blue" | "green";
export type Mode = "compare" | "solve";

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [route, go] = useRoute();
  const wide = useMedia("(min-width: 1100px)");
  const [drawer, setDrawer] = useState(false);
  const [mode, setMode] = usePersisted<Mode>("ks-mode", "compare");
  const [boardTheme, setBoardTheme] = usePersisted<BoardTheme>("ks-board", "brown");
  const [filters, setFilters] = usePersisted<Filters | null>("ks-filters-v1", null);

  useEffect(() => {
    fetch("data/puzzles.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: Dataset) => setData(d))
      .catch((e: Error) => setError(e.message));
  }, []);

  const keys = useMemo(() => data?.models.map((m) => m.key) ?? [], [data]);
  const f = useMemo<Filters>(() => {
    const base = defaultFilters(keys);
    return filters ? { ...base, ...filters, want: { ...base.want, ...filters.want } } : base;
  }, [filters, keys]);
  const list = useMemo(() => (data ? applyFilters(data, f) : []), [data, f]);

  const current = useMemo(() => {
    if (!data || route.view !== "puzzles") return null;
    if (route.id) return data.puzzles.find((p) => p.id === route.id) ?? null;
    return list[0] ?? data.puzzles[0];
  }, [data, route, list]);

  const open = useCallback(
    (id: string) => {
      go(`/p/${id}`);
      setDrawer(false);
    },
    [go],
  );

  const step = useCallback(
    (dir: 1 | -1) => {
      if (!list.length || !current) return;
      const i = list.findIndex((p) => p.id === current.id);
      const j = i < 0 ? 0 : (i + dir + list.length) % list.length;
      open(list[j].id);
    },
    [list, current, open],
  );

  const random = useCallback(() => {
    if (!list.length) return;
    open(list[Math.floor(Math.random() * list.length)].id);
  }, [list, open]);

  useEffect(() => {
    document.body.classList.toggle("no-scroll", drawer && !wide);
  }, [drawer, wide]);

  const sidebar = data && (
    <PuzzleList
      data={data}
      list={list}
      filters={f}
      setFilters={(nf) => setFilters(nf)}
      currentId={current?.id ?? null}
      onOpen={open}
    />
  );

  return (
    <div className="app">
      <Header view={route.view} onMenu={() => setDrawer(true)} showMenu={!wide && route.view === "puzzles"} />
      {error && (
        <div className="state-msg" role="alert">
          Could not load the puzzle data ({error}).
        </div>
      )}
      {!data && !error && <div className="state-msg">Loading 2,000 puzzles…</div>}
      {data && route.view === "results" && <Results data={data} />}
      {data && route.view === "about" && <About data={data} />}
      {data && route.view === "puzzles" && (
        <main className="workspace">
          {wide ? (
            <aside className="sidebar">{sidebar}</aside>
          ) : (
            <>
              <div className={`drawer-scrim${drawer ? " open" : ""}`} onClick={() => setDrawer(false)} />
              <aside className={`drawer${drawer ? " open" : ""}`} aria-hidden={!drawer} aria-label="Puzzle list">
                <div className="drawer-head">
                  <strong>Puzzles</strong>
                  <button className="icon-btn" onClick={() => setDrawer(false)} aria-label="Close puzzle list">
                    <IconClose />
                  </button>
                </div>
                {drawer && sidebar}
              </aside>
            </>
          )}
          {current ? (
            <PuzzleView
              key={`${current.id}-${mode}`}
              data={data}
              puzzle={current}
              position={list.findIndex((p) => p.id === current.id)}
              total={list.length}
              mode={mode}
              setMode={setMode}
              boardTheme={boardTheme}
              setBoardTheme={setBoardTheme}
              onNext={() => step(1)}
              onPrev={() => step(-1)}
              onRandom={random}
            />
          ) : (
            <div className="state-msg">
              {route.view === "puzzles" && route.id ? `No puzzle with id ${route.id}.` : "No puzzle matches these filters."}
            </div>
          )}
        </main>
      )}
    </div>
  );
}

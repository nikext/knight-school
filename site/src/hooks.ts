import { useCallback, useEffect, useState } from "react";

export type Route = { view: "puzzles"; id: string | null } | { view: "results" } | { view: "about" };

function parse(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  if (h === "results") return { view: "results" };
  if (h === "about") return { view: "about" };
  const m = h.match(/^p\/([A-Za-z0-9]+)/);
  return { view: "puzzles", id: m ? m[1] : null };
}

export function useRoute(): [Route, (r: string) => void] {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((r: string) => {
    window.location.hash = r;
  }, []);
  return [route, go];
}

/** State kept in localStorage; works (unsaved) when storage is unavailable. */
export function usePersisted<T>(key: string, init: T, merge?: (saved: unknown) => T): [T, (v: T | ((p: T) => T)) => void] {
  const [v, setV] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw != null) return merge ? merge(JSON.parse(raw)) : (JSON.parse(raw) as T);
    } catch {
      /* private mode or bad JSON */
    }
    return init;
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(v));
    } catch {
      /* not saved */
    }
  }, [key, v]);
  return [v, setV];
}

export function useMedia(query: string): boolean {
  const [hit, setHit] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setHit(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return hit;
}

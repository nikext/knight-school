import { useEffect, useState } from "react";
import { IconGithub, IconList, IconMoon, IconSun } from "./Icons";

const REPO = "https://github.com/nikext/knight-school";

function currentTheme(): "light" | "dark" {
  const t = document.documentElement.dataset.theme;
  if (t === "light" || t === "dark") return t;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function Header({ view, onMenu, showMenu }: { view: string; onMenu: () => void; showMenu: boolean }) {
  const [theme, setTheme] = useState(currentTheme);
  // follow the OS until the viewer picks a theme
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => setTheme(currentTheme());
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  const toggle = () => {
    const t = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = t;
    setTheme(t);
    try {
      localStorage.setItem("ks-theme", t);
    } catch {
      /* not saved */
    }
  };
  const tab = (href: string, label: string, active: boolean) => (
    <a href={href} className={`tab${active ? " active" : ""}`} aria-current={active ? "page" : undefined}>
      {label}
    </a>
  );
  return (
    <header className="topbar">
      <div className="topbar-inner">
        {showMenu && (
          <button className="icon-btn menu-btn" onClick={onMenu} aria-label="Open puzzle list">
            <IconList />
          </button>
        )}
        <a href="#/" className="brand" aria-label="Knight School, puzzle browser">
          <span className="brand-mark" aria-hidden="true">♞</span>
          <span className="brand-name">Knight School</span>
        </a>
        <nav className="tabs" aria-label="Sections">
          {tab("#/", "Puzzles", view === "puzzles")}
          {tab("#/results", "Results", view === "results")}
          {tab("#/about", "About", view === "about")}
        </nav>
        <div className="topbar-actions">
          <a className="icon-btn" href={REPO} target="_blank" rel="noreferrer" aria-label="Source code on GitHub" title="Source on GitHub">
            <IconGithub />
          </a>
          <button className="icon-btn" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} title="Toggle theme">
            {theme === "dark" ? <IconSun /> : <IconMoon />}
          </button>
        </div>
      </div>
    </header>
  );
}

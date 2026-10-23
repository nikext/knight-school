"""Checkpoints off the VM (TRAINING.md §7): push, find the latest, pull, prune.

The trainer saves `checkpoint-<step>/` locally; each one is copied to
`<root>/checkpoint-<step>/` and gets a `_COMPLETE` object last, so a copy
cut off by a preemption is never resumed from. The root is
`gs://BUCKET/runs/<id>/ckpt` in the cloud, or a local directory on the laptop
(the same code path, for the wiring test).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Protocol

COMPLETE = "_COMPLETE"
_CKPT = re.compile(r"(?:^|/)checkpoint-(\d+)/")


class Store(Protocol):
    def names(self, root: str) -> list[str]:
        """Object names relative to root."""
        ...

    def get(self, root: str, name: str, dest: Path) -> None: ...

    def put(self, path: Path, root: str, name: str) -> None: ...

    def rm(self, root: str, name: str) -> None: ...


class LocalStore:
    def names(self, root: str) -> list[str]:
        r = Path(root)
        return (
            [p.relative_to(r).as_posix() for p in r.rglob("*") if p.is_file()] if r.exists() else []
        )

    def get(self, root: str, name: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(root) / name, dest)

    def put(self, path: Path, root: str, name: str) -> None:
        d = Path(root) / name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, d)

    def rm(self, root: str, name: str) -> None:
        p = Path(root) / name
        p.unlink(missing_ok=True)
        for d in p.parents:  # drop emptied dirs, as GCS has none
            if d == Path(root) or any(d.iterdir()):
                break
            d.rmdir()


class GcsStore:
    def __init__(self) -> None:
        from ks.cloud import gcs

        self.gcs = gcs
        self.s = gcs._session(write=True)

    def names(self, root: str) -> list[str]:
        prefix = self.gcs.split(root.rstrip("/") + "/")[1]
        return [n.removeprefix(prefix) for n in self.gcs.list_names(root.rstrip("/") + "/", self.s)]

    def get(self, root: str, name: str, dest: Path) -> None:
        self.gcs.download(f"{root.rstrip('/')}/{name}", dest, self.s)

    def put(self, path: Path, root: str, name: str) -> None:
        self.gcs.upload(path, f"{root.rstrip('/')}/{name}", self.s)

    def rm(self, root: str, name: str) -> None:
        self.gcs.delete(f"{root.rstrip('/')}/{name}", self.s)


def store_for(root: str) -> Store:
    return GcsStore() if root.startswith("gs://") else LocalStore()


def steps(store: Store, root: str) -> dict[int, list[str]]:
    """step -> object names, for every checkpoint under root (complete or not)."""
    out: dict[int, list[str]] = {}
    for n in store.names(root):
        if m := _CKPT.match(n):
            out.setdefault(int(m.group(1)), []).append(n)
    return out


def latest(store: Store, root: str) -> int | None:
    """The newest step whose copy finished."""
    done = [s for s, names in steps(store, root).items() if f"checkpoint-{s}/{COMPLETE}" in names]
    return max(done) if done else None


def push(store: Store, local: Path, root: str, keep: int) -> int:
    """Copy one local `checkpoint-<step>` dir, mark it complete, prune to `keep`. Returns files."""
    m = re.fullmatch(r"checkpoint-(\d+)", local.name)
    if m is None:
        raise ValueError(f"not a checkpoint dir: {local}")
    files = [p for p in sorted(local.rglob("*")) if p.is_file()]
    for p in files:
        store.put(p, root, f"{local.name}/{p.relative_to(local).as_posix()}")
    marker = local / COMPLETE
    marker.write_text("")
    store.put(marker, root, f"{local.name}/{COMPLETE}")
    prune(store, root, keep)
    return len(files)


def prune(store: Store, root: str, keep: int) -> list[int]:
    """Delete all but the newest `keep` complete checkpoints (and older partial ones)."""
    all_ = steps(store, root)
    done = sorted(
        (s for s, names in all_.items() if f"checkpoint-{s}/{COMPLETE}" in names), reverse=True
    )
    if not done:
        return []
    kept = set(done[:keep])
    oldest_kept = min(kept)
    gone = [s for s in all_ if s not in kept and s < oldest_kept]
    for s in gone:
        # the marker goes first, so a half-deleted checkpoint is never taken for a complete one
        names = sorted(all_[s], key=lambda n: not n.endswith(COMPLETE))
        for n in names:
            store.rm(root, n)
    return sorted(gone)


def pull(store: Store, root: str, step: int, dest: Path) -> Path:
    """Copy checkpoint-<step> into dest/checkpoint-<step> and return that path."""
    out = dest / f"checkpoint-{step}"
    for n in steps(store, root)[step]:
        store.get(root, n, dest / n)
    return out

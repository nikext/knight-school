"""Manifests for built artefacts, and the "skip if unchanged" rule `make data` relies on.

A step's fingerprint hashes its inputs' content, its parameters and the source
of the modules that produce it. If the manifest on disk has the same
fingerprint and every output still hashes to what the manifest says, the step
is skipped. The git SHA is recorded for provenance only (it changes on every
commit, which must not re-run four hours of Stockfish).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from ks.cloud.config import REPO

MANIFESTS = REPO / "manifests"
DATA = REPO / "data"
SETS = REPO / "evals" / "sets"
DATA_VERSION = "v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def sha256_paths(paths: Iterable[Path]) -> str:
    """One hash over several files (e.g. a directory of shards), in sorted path order."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.name.encode())
        h.update(sha256_file(p).encode())
    return h.hexdigest()


def git_sha() -> str:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
        ).stdout.strip()

    sha = run("rev-parse", "--short=12", "HEAD") or "unknown"
    return sha + ("-dirty" if run("status", "--porcelain", "--", "ks") else "")


def fingerprint(inputs: dict[str, str], params: dict[str, Any], code: list[ModuleType]) -> str:
    """inputs: name -> sha256. code: the modules whose source decides the output."""
    h = hashlib.sha256()
    h.update(json.dumps({"inputs": inputs, "params": params}, sort_keys=True).encode())
    for mod in code:
        assert mod.__file__
        h.update(Path(mod.__file__).read_bytes())
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO))


def manifest_path(name: str) -> Path:
    return MANIFESTS / f"{name}.json"


def load(name: str) -> dict[str, Any] | None:
    p = manifest_path(name)
    return json.loads(p.read_text()) if p.exists() else None


def output_sha(name: str) -> str:
    """The recorded sha256 of a step's (single or combined) output, for downstream fingerprints."""
    m = load(name)
    if m is None:
        raise FileNotFoundError(f"manifest {name} missing; run its step first")
    return m["sha256"]


def _outputs_sha(outputs: list[Path]) -> str:
    """One file: its sha256. Several, or a directory of shards: a hash over all of them."""
    if not outputs:
        return ""
    if len(outputs) == 1 and outputs[0].is_file():
        return sha256_file(outputs[0])
    files: list[Path] = []
    for o in outputs:
        files.extend(sorted(x for x in o.rglob("*") if x.is_file()) if o.is_dir() else [o])
    return sha256_paths(files)


def up_to_date(name: str, fp: str, outputs: list[Path]) -> bool:
    m = load(name)
    if m is None or m.get("fingerprint") != fp or not all(o.exists() for o in outputs):
        return False
    return _outputs_sha(outputs) == m.get("sha256")


def write(name: str, fp: str, outputs: list[Path], **fields: Any) -> dict[str, Any]:
    """Write manifests/<name>.json. `fields` carries counts, seeds, versions and hits."""
    doc: dict[str, Any] = {
        "name": name,
        "data_version": DATA_VERSION,
        "outputs": [rel(o) for o in outputs],
        "sha256": _outputs_sha(outputs),
        "fingerprint": fp,
        "git_sha": git_sha(),
        "built_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        **fields,
    }
    MANIFESTS.mkdir(exist_ok=True)
    manifest_path(name).write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    return doc

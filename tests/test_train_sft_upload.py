"""SFT checkpoint copies run in the background, one at a time, and free the older local copy."""

from __future__ import annotations

from pathlib import Path

from ks.train import ckpt as kc
from ks.train.sft import Uploader


def make(local: Path, step: int) -> Path:
    d = local / f"checkpoint-{step}"
    d.mkdir(parents=True)
    (d / "optimizer.pt").write_text(f"o{step}")
    return d


def test_uploader_copies_marks_and_frees_the_older_local(tmp_path: Path):
    store, root, logs = kc.LocalStore(), str(tmp_path / "remote"), []
    up = Uploader(store, root, keep=1, log=logs.append)
    up.start(make(tmp_path / "w", 10))
    up.wait()
    assert kc.latest(store, root) == 10
    up.start(make(tmp_path / "w", 20))  # waits for nothing: the first copy is done
    up.wait()
    assert kc.latest(store, root) == 20 and sorted(kc.steps(store, root)) == [20]
    assert [p.name for p in (tmp_path / "w").iterdir()] == ["checkpoint-20"]
    assert any("checkpoint-20: 1 files" in s for s in logs)


def test_a_failed_copy_is_logged_not_raised(tmp_path: Path):
    class Broken(kc.LocalStore):
        def put(self, path: Path, root: str, name: str) -> None:
            raise OSError("network down")

    logs: list[str] = []
    up = Uploader(Broken(), str(tmp_path / "remote"), keep=1, log=logs.append)
    up.start(make(tmp_path / "w", 10))
    up.wait()
    assert any("FAILED" in s for s in logs)
    assert (tmp_path / "w" / "checkpoint-10").exists()  # kept: nothing else holds it

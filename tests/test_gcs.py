from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ks.cloud import gcs


class Resp:
    def __init__(self, body: Any = None, data: bytes = b"") -> None:
        self.body, self.data = body, data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Any:
        return self.body

    def iter_content(self, n: int):
        yield self.data

    def __enter__(self) -> Resp:
        return self

    def __exit__(self, *a: Any) -> None:
        pass


class Session:
    def __init__(self, pages: list[dict[str, Any]], files: dict[str, bytes]) -> None:
        self.pages, self.files, self.calls = pages, files, []

    def get(self, url: str, params: dict[str, str], **kw: Any) -> Resp:
        self.calls.append((url, dict(params)))
        if params.get("alt") == "media":
            return Resp(data=self.files[url.rsplit("/", 1)[1]])
        return Resp(self.pages.pop(0))


def test_split():
    assert gcs.split("gs://b/a/b.parquet") == ("b", "a/b.parquet")
    with pytest.raises(ValueError):
        gcs.split("/local/path")


def test_list_follows_pages():
    s = Session(
        [{"items": [{"name": "p/a"}], "nextPageToken": "t"}, {"items": [{"name": "p/b"}]}], {}
    )
    assert gcs.list_names("gs://bkt/p/", s) == ["p/a", "p/b"]
    assert s.calls[0][0].endswith("/b/bkt/o") and s.calls[1][1]["pageToken"] == "t"


def test_download_quotes_the_object_name(tmp_path: Path):
    s = Session([], {"runs%2Fx%2Fadapter.bin": b"weights"})
    out = gcs.download("gs://bkt/runs/x/adapter.bin", tmp_path / "a" / "adapter.bin", s)
    assert out.read_bytes() == b"weights"


class WriteSession(Session):
    def __init__(self) -> None:
        super().__init__([], {})
        self.posts: list[tuple[str, dict[str, str], bytes]] = []

    def post(self, url: str, params: dict[str, str], data: Any, **kw: Any) -> Resp:
        self.posts.append((url, dict(params), data.read()))
        return Resp()


def test_push_keeps_relative_paths(tmp_path: Path, monkeypatch):
    (tmp_path / "eval" / "dev500").mkdir(parents=True)
    (tmp_path / "eval" / "dev500" / "m.json").write_text("{}")
    (tmp_path / "done").mkdir()
    (tmp_path / "done" / "eval-m").write_text("")
    s = WriteSession()
    monkeypatch.setattr(gcs, "_session", lambda write=False: s)
    assert gcs.push(tmp_path, "gs://bkt/runs/x/attempts/2/out/") == 2
    names = sorted(p[1]["name"] for p in s.posts)
    assert names == [
        "runs/x/attempts/2/out/done/eval-m",
        "runs/x/attempts/2/out/eval/dev500/m.json",
    ]
    assert all(p[0].endswith("/upload/storage/v1/b/bkt/o") for p in s.posts)

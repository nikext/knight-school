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

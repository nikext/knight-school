"""Minimal GCS access for code that runs inside the train image (ADR-016).

The vLLM base image ships google-auth but an inconsistent google-api-core /
opentelemetry pair, so google-cloud-storage can't be installed next to it
without upgrading packages under vLLM. Jobs only download inputs and
checkpoints and push their outputs, so this talks to the JSON API directly
with google-auth credentials (the VM's service account, or ADC on the laptop).

    python -m ks.cloud.gcs push /out gs://bucket/runs/<id>/attempts/<n>/out
    python -m ks.cloud.gcs pull gs://bucket/runs/<id>/attempts/1/out /out
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

API = "https://storage.googleapis.com/storage/v1"
UPLOAD = "https://storage.googleapis.com/upload/storage/v1"
READ_WRITE = "https://www.googleapis.com/auth/devstorage.read_write"


RETRIES = 6  # 1 + 2 + 4 + 8 + 16 s of backoff
_sleep = time.sleep


def _retry[T](fn: Callable[[], T]) -> T:
    """Run a request, retrying dropped connections and 408/429/5xx with backoff.

    m3-tput-h100 died on one `RemoteDisconnected` while copying a checkpoint: the session's
    kept-alive connection had been closed by the server during ten idle minutes.
    """
    import requests

    for attempt in range(RETRIES):
        try:
            return fn()
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if (code not in (408, 429) and code < 500) or attempt == RETRIES - 1:
                raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == RETRIES - 1:
                raise
        _sleep(2**attempt)
    raise AssertionError("unreachable")


def split(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"not a gs:// uri: {uri}")
    bucket, _, name = uri.removeprefix("gs://").partition("/")
    return bucket, name


def _session(write: bool = False) -> Any:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    scope = READ_WRITE if write else "https://www.googleapis.com/auth/devstorage.read_only"
    creds, _ = google.auth.default(scopes=[scope])
    return AuthorizedSession(creds)


def list_names(uri: str, session: Any = None) -> list[str]:
    """Object names under a gs:// prefix."""
    bucket, prefix = split(uri)
    s = session or _session()
    names: list[str] = []
    token = None
    while True:
        params = {"prefix": prefix, "fields": "items(name),nextPageToken"}
        if token:
            params["pageToken"] = token

        def page(params: dict[str, str] = params) -> Any:
            r = s.get(f"{API}/b/{bucket}/o", params=params, timeout=60)
            r.raise_for_status()
            return r.json()

        body = _retry(page)
        names += [it["name"] for it in body.get("items", [])]
        token = body.get("nextPageToken")
        if not token:
            return names


def download(uri: str, dest: Path, session: Any = None) -> Path:
    bucket, name = split(uri)
    s = session or _session()
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{API}/b/{bucket}/o/{quote(name, safe='')}"

    def get() -> None:
        with s.get(url, params={"alt": "media"}, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)

    _retry(get)
    return dest


def download_prefix(uri: str, dest: Path) -> Path:
    """Copy every object under a gs:// prefix into dest, keeping relative paths."""
    bucket, prefix = split(uri)
    prefix = prefix.rstrip("/") + "/"
    s = _session()
    for name in list_names(f"gs://{bucket}/{prefix}", s):
        if not name.endswith("/"):
            download(f"gs://{bucket}/{name}", dest / name.removeprefix(prefix), s)
    return dest


def upload(path: Path, uri: str, session: Any = None) -> None:
    bucket, name = split(uri)
    s = session or _session(write=True)

    def post() -> None:
        with open(path, "rb") as f:  # reopened per try: a failed try consumed the stream
            r = s.post(
                f"{UPLOAD}/b/{bucket}/o",
                params={"uploadType": "media", "name": name},
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=600,
            )
        r.raise_for_status()

    _retry(post)


def delete(uri: str, session: Any = None) -> None:
    bucket, name = split(uri)
    s = session or _session(write=True)

    def rm() -> None:
        r = s.delete(f"{API}/b/{bucket}/o/{quote(name, safe='')}", timeout=60)
        if r.status_code != 404:  # already gone is fine
            r.raise_for_status()

    _retry(rm)


def push(src: Path, uri: str) -> int:
    """Upload every file under src to the gs:// prefix (overwriting). Returns the file count."""
    prefix = uri.rstrip("/")
    s = _session(write=True)
    files = [p for p in sorted(src.rglob("*")) if p.is_file()]
    for p in files:
        upload(p, f"{prefix}/{p.relative_to(src).as_posix()}", s)
    return len(files)


def main(argv: list[str] | None = None) -> None:
    import sys

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or args[0] not in ("push", "pull"):
        raise SystemExit("usage: python -m ks.cloud.gcs push DIR gs://... | pull gs://... DIR")
    if args[0] == "push":
        print(f"pushed {push(Path(args[1]), args[2])} files to {args[2]}")
    else:
        download_prefix(args[1], Path(args[2]))
        print(f"pulled {args[1]} into {args[2]}")


if __name__ == "__main__":
    main()

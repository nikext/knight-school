"""Minimal GCS reads for code that runs inside the train image (ADR-016).

The vLLM base image ships google-auth but an inconsistent google-api-core /
opentelemetry pair, so google-cloud-storage can't be installed next to it
without upgrading packages under vLLM. Jobs only need to download inputs and
checkpoints, so this talks to the JSON API directly with google-auth
credentials (the VM's service account, or ADC on the laptop).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

API = "https://storage.googleapis.com/storage/v1"


def split(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"not a gs:// uri: {uri}")
    bucket, _, name = uri.removeprefix("gs://").partition("/")
    return bucket, name


def _session() -> Any:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_only"])
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
        r = s.get(f"{API}/b/{bucket}/o", params=params, timeout=60)
        r.raise_for_status()
        body = r.json()
        names += [it["name"] for it in body.get("items", [])]
        token = body.get("nextPageToken")
        if not token:
            return names


def download(uri: str, dest: Path, session: Any = None) -> Path:
    bucket, name = split(uri)
    s = session or _session()
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{API}/b/{bucket}/o/{quote(name, safe='')}"
    with s.get(url, params={"alt": "media"}, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
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

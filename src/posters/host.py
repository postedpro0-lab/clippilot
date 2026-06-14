"""Publish a clip as a public GitHub Release asset so IG/TikTok can pull it.

Instagram and TikTok both ingest video by fetching a public URL (they don't
accept a raw multipart upload the simple way). The cheapest $0 host we already
have is a GitHub Release on the same repo.
"""
import time
from pathlib import Path

import requests

from ..config import env

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"


def _repo():
    # In Actions, GITHUB_REPOSITORY is "owner/name". Allow override via PUBLIC_REPO.
    return env("PUBLIC_REPO") or env("GITHUB_REPOSITORY")


def _headers():
    tok = env("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}


def _ensure_release(repo, tag="clips"):
    r = requests.get(f"{API}/repos/{repo}/releases/tags/{tag}", headers=_headers())
    if r.status_code == 200:
        return r.json()
    r = requests.post(
        f"{API}/repos/{repo}/releases",
        headers=_headers(),
        json={"tag_name": tag, "name": "ClipPilot clips", "body": "Auto-published clips."},
    )
    r.raise_for_status()
    return r.json()


def publish(clip_path: Path):
    """Upload the clip and return its public download URL."""
    repo = _repo()
    if not repo or not env("GITHUB_TOKEN"):
        raise RuntimeError(
            "host.publish needs GITHUB_TOKEN + a repo (GITHUB_REPOSITORY/PUBLIC_REPO). "
            "Instagram/TikTok posting requires this."
        )
    rel = _ensure_release(repo)
    name = f"{int(time.time())}_{clip_path.name}"
    upload_url = rel["upload_url"].split("{")[0]
    with open(clip_path, "rb") as f:
        r = requests.post(
            f"{upload_url}?name={name}",
            headers={**_headers(), "Content-Type": "video/mp4"},
            data=f.read(),
        )
    r.raise_for_status()
    url = r.json()["browser_download_url"]
    print(f"[host] published {name}")
    return url

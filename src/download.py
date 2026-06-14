"""Download a YouTube video with yt-dlp (Python API)."""
from pathlib import Path

import yt_dlp

from .config import WORK, env


def download(video_url, video_id):
    out_path = WORK / f"{video_id}.mp4"
    if out_path.exists():
        return out_path

    base_opts = {
        # cap at 1080p source — plenty for a 1080x1920 crop, keeps it fast/small.
        # No ext constraint: merge_output_format remuxes to mp4, and forcing
        # ext=mp4/m4a breaks on player clients that only expose webm/opus.
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": str(WORK / f"{video_id}.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
    }

    # If a cookies file is provided (YOUTUBE_COOKIES path in env), use it — most
    # reliable way past YouTube's "confirm you're not a bot" on datacenter IPs.
    cookies = env("YOUTUBE_COOKIES_FILE")
    if cookies and Path(cookies).exists():
        base_opts["cookiefile"] = cookies

    # With cookies the default "web" client works and exposes the richest
    # formats, so try it first. The alternate clients are fallbacks for the
    # cookieless / datacenter-IP case. None = let yt-dlp pick the default.
    client_attempts = [
        None,
        ["tv"],
        ["web_safari"],
        ["mweb"],
        ["ios"],
        ["android"],
    ]

    print(f"[download] {video_url}")
    last_err = None
    for clients in client_attempts:
        opts = dict(base_opts)
        if clients is not None:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([video_url])
            break  # success
        except Exception as e:
            last_err = e
            print(f"[download] player_client={clients} failed: {str(e)[:120]}")
            continue
    else:
        # all clients failed
        raise last_err

    # yt-dlp may produce .mkv/.webm if merge target differs; normalize
    if not out_path.exists():
        for cand in WORK.glob(f"{video_id}.*"):
            if cand.suffix in (".mp4", ".mkv", ".webm"):
                return cand
    return out_path

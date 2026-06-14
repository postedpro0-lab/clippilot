"""Download a YouTube video with yt-dlp (Python API)."""
from pathlib import Path

import yt_dlp

from .config import WORK, env


def download(video_url, video_id):
    out_path = WORK / f"{video_id}.mp4"
    if out_path.exists():
        return out_path

    base_opts = {
        # cap at 1080p source — plenty for a 1080x1920 crop, keeps it fast/small
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
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

    # YouTube bot-blocks datacenter IPs (e.g. GitHub Actions) on the default
    # "web" player client. Try alternate player clients in order; some bypass the
    # check without cookies. First one that downloads wins.
    client_attempts = [
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

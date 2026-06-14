"""Download a YouTube video with yt-dlp (Python API)."""
from pathlib import Path

import yt_dlp

from .config import WORK


def download(video_url, video_id):
    out_path = WORK / f"{video_id}.mp4"
    if out_path.exists():
        return out_path

    ydl_opts = {
        # cap at 1080p source — plenty for a 1080x1920 crop, keeps it fast/small
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
        "outtmpl": str(WORK / f"{video_id}.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    print(f"[download] {video_url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    # yt-dlp may produce .mkv/.webm if merge target differs; normalize
    if not out_path.exists():
        for cand in WORK.glob(f"{video_id}.*"):
            if cand.suffix in (".mp4", ".mkv", ".webm"):
                return cand
    return out_path

"""Download a YouTube video via the yt-dlp CLI.

We shell out to the `yt-dlp` binary (rather than the Python API) so the
bgutil PO-token provider plugin engages exactly as it does on the command
line — that's the path proven to get past YouTube's bot check + SABR
streaming. Cookies + the PO-token provider together unblock downloads.
"""
import subprocess
import sys
from pathlib import Path

from .config import WORK, env

# Invoke yt-dlp as a module of the *current* interpreter so the right venv
# (with the PO-token plugin installed) is always used — both locally and in CI.
YTDLP = [sys.executable, "-m", "yt_dlp"]

# cap at 1080p source — plenty for a 1080x1920 crop. No ext constraint: the
# merge step remuxes to mp4, and forcing ext=mp4/m4a breaks on clients that
# only expose webm/opus.
FORMAT = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"


def get_duration(video_url):
    """Return the video's duration in seconds (metadata only, no download),
    or None if it can't be determined. Used to skip Shorts."""
    try:
        r = subprocess.run(
            [*YTDLP, "--no-warnings", "--skip-download", "--print", "%(duration)s", video_url],
            capture_output=True, text=True, timeout=90,
        )
        for line in reversed(r.stdout.strip().splitlines()):
            line = line.strip()
            try:
                return float(line)
            except ValueError:
                continue
    except Exception as e:
        print(f"[download] duration probe failed: {str(e)[:100]}")
    return None


def download(video_url, video_id):
    out_path = WORK / f"{video_id}.mp4"
    if out_path.exists():
        return out_path

    base = [
        *YTDLP,
        "-f", FORMAT,
        "--merge-output-format", "mp4",
        "-o", str(WORK / f"{video_id}.%(ext)s"),
        "--no-playlist",
        "--no-warnings",
        "--retries", "5",
        "--fragment-retries", "5",
    ]

    # Cookies (written from the YOUTUBE_COOKIES_B64 secret) get past the
    # "confirm you're not a bot" check on datacenter IPs.
    cookies = env("YOUTUBE_COOKIES_FILE")
    if cookies and Path(cookies).exists():
        base += ["--cookies", cookies]

    # Default client first (PO-token provider engages and exposes the richest
    # formats); alternate clients are fallbacks. None = yt-dlp's default.
    client_attempts = [None, "tv", "web_safari", "mweb"]

    print(f"[download] {video_url}")
    last_err = ""
    for client in client_attempts:
        cmd = list(base)
        if client:
            cmd += ["--extractor-args", f"youtube:player_client={client}"]
        cmd.append(video_url)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            break  # success
        except subprocess.CalledProcessError as e:
            last_err = (e.stderr or e.stdout or "").strip()
            print(f"[download] client={client} failed: {last_err[:150]}")
            continue
    else:
        raise RuntimeError(f"yt-dlp failed for {video_url}: {last_err[:300]}")

    if out_path.exists():
        return out_path
    # yt-dlp may produce .mkv/.webm if merge target differs; normalize
    for cand in WORK.glob(f"{video_id}.*"):
        if cand.suffix in (".mp4", ".mkv", ".webm"):
            return cand
    return out_path

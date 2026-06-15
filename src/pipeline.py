"""End-to-end: watch channel -> download -> transcribe -> clip -> post."""
import re
import time
import traceback
from pathlib import Path

from . import monitor, download, transcribe, moments, clipper, resolve
from .config import load_config, WORK
from .posters import youtube, instagram, tiktok, snapchat


def _build_caption(cfg, title):
    cap = cfg["caption_template"].format(title=title)
    extra = " ".join(cfg.get("extra_hashtags", []))
    return (cap + " " + extra).strip()


def _post_clip(cfg, clip_path, title, caption, posted_counter):
    targets = cfg["post_to"]
    spacing = cfg.get("post_spacing_seconds", 90)

    if targets.get("youtube"):
        try:
            youtube.post(clip_path, title, caption, cfg.get("extra_hashtags", []))
            posted_counter["youtube"] += 1
            time.sleep(spacing)
        except Exception as e:
            print(f"[pipeline] youtube post failed: {e}")

    if targets.get("instagram"):
        try:
            instagram.post(clip_path, caption)
            posted_counter["instagram"] += 1
            time.sleep(spacing)
        except Exception as e:
            print(f"[pipeline] instagram post failed: {e}")

    if targets.get("tiktok"):
        try:
            tiktok.post(clip_path, caption)
            posted_counter["tiktok"] += 1
            time.sleep(spacing)
        except Exception as e:
            print(f"[pipeline] tiktok post failed: {e}")

    if targets.get("snapchat"):
        try:
            snapchat.post(clip_path, caption, target=cfg.get("snapchat_target", "SPOTLIGHT"))
            posted_counter["snapchat"] += 1
            time.sleep(spacing)
        except Exception as e:
            print(f"[pipeline] snapchat post failed: {e}")


def process_video(cfg, video, source_label="channel"):
    print(f"\n=== [{source_label}] Processing: {video['title']} ({video['id']}) ===")
    src = download.download(video["url"], video["id"])

    _segments, words = transcribe.transcribe(
        src, model_name=cfg["whisper_model"], language=cfg["whisper_language"]
    )

    duration = words[-1]["end"] if words else None
    windows = moments.pick_moments(
        words,
        max_clip_seconds=cfg.get("max_clip_seconds", 60),
        min_clip_seconds=cfg.get("min_clip_seconds", 8),
        max_clips=cfg["max_clips_per_video"],
        video_duration=duration,
        source=src,
        moment_pause=cfg.get("moment_pause_seconds", 1.0),
        scene_quiet=cfg.get("scene_quiet_seconds", 3.0),
    )

    caption = _build_caption(cfg, video["title"])
    posted = {"youtube": 0, "instagram": 0, "tiktok": 0, "snapchat": 0}

    out_dir = WORK / source_label
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, (start, end) in enumerate(windows, 1):
        clip_path = out_dir / f"{video['id']}_clip{i}.mp4"
        try:
            clipper.make_clip(
                src, words, start, end, cfg["out_width"], cfg["out_height"], clip_path
            )
        except Exception:
            print(f"[pipeline] clip {i} failed:\n{traceback.format_exc()}")
            continue
        _post_clip(cfg, clip_path, video["title"], caption, posted)

    print(f"[pipeline] done: {posted}")
    monitor.mark_done(video["id"])
    # tidy the big source file to keep CI disk/footprint small
    try:
        Path(src).unlink(missing_ok=True)
    except Exception:
        pass


def run():
    cfg = load_config()
    channels = cfg.get("channels") or []
    if not channels:
        raise SystemExit("Add at least one channel to `channels:` in config.yaml")

    backlog = cfg.get("process_backlog", False)
    for entry in channels:
        try:
            cid = resolve.channel_id(entry)
        except Exception as e:
            print(f"[pipeline] could not resolve '{entry}': {e}")
            continue
        label = resolve.label(entry)
        print(f"\n##### Channel: {entry} -> {cid} (folder: {label}) #####")
        new_videos = monitor.find_new_videos(
            cid, process_backlog=backlog,
            min_source_seconds=cfg.get("min_source_seconds", 90),
        )
        for v in new_videos:
            try:
                process_video(cfg, v, source_label=label)
            except Exception:
                print(f"[pipeline] video {v['id']} failed:\n{traceback.format_exc()}")


if __name__ == "__main__":
    run()

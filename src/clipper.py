"""Cut a window to a 9:16 vertical clip with burned-in captions via ffmpeg."""
import subprocess
from pathlib import Path

from .config import WORK


def _fmt_ass_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _chunk_words(words, max_words=4):
    """Group words into short caption chunks (max ~4 words) for readability."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def _build_ass(words, start, end, out_w, out_h, ass_path):
    """Write an .ass subtitle file (times relative to clip start)."""
    fontsize = int(out_h * 0.052)
    margin_v = int(out_h * 0.18)  # sit captions in lower third
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {out_w}
PlayResY: {out_h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Pop,Arial,{fontsize},&H00FFFFFF,&H00000000,&H80000000,1,1,4,2,2,60,60,{margin_v}

[Events]
Format: Layer, Start, End, Style, Text
"""
    lines = []
    clip_words = [w for w in words if start <= w["start"] < end]
    for chunk in _chunk_words(clip_words, max_words=4):
        c_start = max(chunk[0]["start"] - start, 0)
        c_end = max(chunk[-1]["end"] - start, c_start + 0.4)
        text = " ".join(w["word"] for w in chunk).replace("\n", " ").upper()
        lines.append(
            f"Dialogue: 0,{_fmt_ass_time(c_start)},{_fmt_ass_time(c_end)},Pop,,0,0,0,,{text}"
        )
    ass_path.write_text(header + "\n".join(lines))


def _run_ffmpeg(source, start, end, vf, out_path):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(source),
        "-t", str(end - start),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def make_clip(source, words, start, end, out_w, out_h, out_path):
    """Produce a 9:16 clip with burned-in captions; fall back to no captions if
    this ffmpeg build lacks the subtitles filter (no libass)."""
    ass_path = Path(str(out_path) + ".ass")
    _build_ass(words, start, end, out_w, out_h, ass_path)

    crop = (
        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h}"
    )
    # libass wants ':' and '\' in the path escaped inside the filtergraph.
    esc = ass_path.as_posix().replace("\\", "\\\\").replace(":", r"\:")
    captioned_vf = f"{crop},subtitles='{esc}'"

    print(f"[clipper] -> {out_path.name} ({start:.0f}-{end:.0f}s)")
    res = _run_ffmpeg(source, start, end, captioned_vf, out_path)
    if res.returncode != 0:
        err = (res.stderr or "")[-400:]
        print(f"[clipper] captioned encode failed, retrying WITHOUT captions: {err}")
        res = _run_ffmpeg(source, start, end, crop, out_path)
        if res.returncode != 0:
            ass_path.unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg failed: {(res.stderr or '')[-400:]}")

    ass_path.unlink(missing_ok=True)
    return out_path

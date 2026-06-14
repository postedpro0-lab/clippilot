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


def make_clip(source, words, start, end, out_w, out_h, out_path):
    """Produce one captioned 9:16 clip."""
    ass_path = Path(str(out_path) + ".ass")
    _build_ass(words, start, end, out_w, out_h, ass_path)

    # scale source to fill the 9:16 frame, center-crop, then burn captions.
    vf = (
        f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
        f"crop={out_w}:{out_h},"
        f"subtitles='{ass_path.as_posix()}'"
    )

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
    print(f"[clipper] -> {out_path.name} ({start:.0f}-{end:.0f}s)")
    subprocess.run(cmd, check=True, capture_output=True)
    ass_path.unlink(missing_ok=True)
    return out_path

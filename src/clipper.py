"""Cut a window to a 9:16 vertical clip with burned-in captions via ffmpeg."""
import subprocess
from pathlib import Path

from .config import WORK


def _fmt_ass_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _clean(word):
    """Uppercase a word and strip chars that would break ASS markup."""
    return word.strip().upper().replace("{", "").replace("}", "").replace("\\", "")


def _group_words(words, max_per=3):
    """Group words into short phrases (<= max_per), breaking early on end
    punctuation so a phrase never spans a natural pause."""
    groups, cur = [], []
    for w in words:
        cur.append(w)
        ends_phrase = w["word"].strip().endswith((".", "!", "?", ",", ":", ";"))
        if len(cur) >= max_per or ends_phrase:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def _build_ass(words, start, end, out_w, out_h, ass_path):
    """Write an .ass file where words pop in one-at-a-time as they're spoken.

    At most a few words are on screen at once (a phrase), each new word
    scale-pops in; the phrase clears before the next. Smart word-wrap +
    generous side margins keep text inside the 9:16 frame (no edge cutoff)."""
    fontsize = int(out_h * 0.050)            # punchy but leaves room to wrap
    margin_v = int(out_h * 0.20)             # lower third, clear of platform UI
    margin_h = int(out_w * 0.10)             # keep words off the L/R edges
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {out_w}
PlayResY: {out_h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Pop,Arial,{fontsize},&H00FFFFFF,&H00000000,&H90000000,1,1,6,2,2,{margin_h},{margin_h},{margin_v}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, Effect, Text
"""
    lines = []
    clip_words = [w for w in words if start <= w["start"] < end]
    groups = _group_words(clip_words, max_per=3)

    for gi, group in enumerate(groups):
        next_group_start = (
            groups[gi + 1][0]["start"] if gi + 1 < len(groups) else end
        )
        # the finished phrase lingers briefly, but never into the next phrase
        hold_end = min(group[-1]["end"] + 0.25, next_group_start)

        for j, w in enumerate(group):
            ev_start = max(w["start"] - start, 0.0)
            if j + 1 < len(group):
                ev_end = group[j + 1]["start"] - start
            else:
                ev_end = hold_end - start
            ev_end = max(ev_end, ev_start + 0.10)

            # cumulative phrase so far; the newest (last) word scale-pops in
            tokens = [_clean(group[k]["word"]) for k in range(j + 1)]
            tokens[-1] = r"{\fscx60\fscy60\t(0,110,\fscx100\fscy100)}" + tokens[-1]
            text = " ".join(tokens)
            lines.append(
                f"Dialogue: 0,{_fmt_ass_time(ev_start)},{_fmt_ass_time(ev_end)},Pop,,0,0,,{text}"
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

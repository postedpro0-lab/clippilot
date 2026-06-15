"""Pick the best clippable MOMENTS from a video.

Key idea: a clip should capture a whole "moment" and only end when the action
is over — i.e. at a real lull, not at the first sentence-end or scene-change.

- With speech: a moment runs until a significant PAUSE in the commentary
  (>= moment_pause seconds). One pause = the play/topic wrapped up.
- Without speech: a moment is a burst of visual activity that ends when the
  footage goes calm (a stable shot with no scene change for >= scene_quiet
  seconds).

Moments are then bounded to <= max_clip_seconds (a moment longer than that is
split, since clips must stay under 60s), tiny moments are merged/dropped, and
the best (or, for silent footage, the most active) are kept, up to max_clips.
No paid AI.
"""
import re
import subprocess
from math import ceil

HOOK_WORDS = {
    "you", "your", "why", "how", "what", "secret", "never", "always", "best",
    "worst", "stop", "mistake", "money", "free", "now", "today", "first",
    "imagine", "crazy", "insane", "actually", "literally", "because", "but",
    "wait", "listen", "watch", "look", "here's", "this", "nobody", "everyone",
    "goal", "wow", "unbelievable", "incredible", "scores", "wins", "history",
}
NUM_RE = re.compile(r"\b\d+\b")
SENT_END_RE = re.compile(r"[.!?]$")
_TOKEN_RE = re.compile(r"[a-z']+")

# Defaults (overridable via pick_moments kwargs / config):
MOMENT_PAUSE = 1.0   # speech gap (s) that means "the moment is over"
SCENE_QUIET = 3.0    # stable-shot length (s) that means "the action settled"


def _tokens(text):
    return _TOKEN_RE.findall(text.lower())


def _score_window(win_words, text, target_len):
    duration = win_words[-1]["end"] - win_words[0]["start"]
    if duration <= 0:
        return 0.0
    density = min(len(win_words) / duration / 3.0, 1.0)
    hook_score = min(len(set(_tokens(text)) & HOOK_WORDS) / 6.0, 1.0)
    num_score = min(len(NUM_RE.findall(text)) / 3.0, 1.0)
    length_score = max(0.0, 1.0 - abs(duration - target_len) / target_len)
    return 0.40 * density + 0.28 * hook_score + 0.10 * num_score + 0.22 * length_score


# ----------------------------- speech path ------------------------------- #

def _moments_by_pause(words, pause):
    """Split words into moments: break only where speech pauses >= `pause`."""
    segs, cur = [], [words[0]]
    for prev, w in zip(words[:-1], words[1:]):
        if w["start"] - prev["end"] >= pause:
            segs.append(cur)
            cur = [w]
        else:
            cur.append(w)
    segs.append(cur)
    return segs


def _split_long(seg, max_len):
    """A moment longer than max_len must be cut (clips stay < 60s). Split into
    roughly-equal chunks at word boundaries (no tiny leftover tail)."""
    dur = seg[-1]["end"] - seg[0]["start"]
    n = ceil(dur / max_len)
    target = dur / n
    out, chunk, chunk_start = [], [seg[0]], seg[0]["start"]
    for w in seg[1:]:
        if (w["end"] - chunk_start) >= target and len(out) < n - 1:
            out.append(chunk)
            chunk, chunk_start = [w], w["start"]
        else:
            chunk.append(w)
    out.append(chunk)
    return out


def _finalize(segs, max_len):
    """Only split over-long moments. Never merge across a lull — each moment is
    its own complete action and stays a separate clip."""
    out = []
    for seg in segs:
        if seg[-1]["end"] - seg[0]["start"] > max_len:
            out.extend(_split_long(seg, max_len))
        else:
            out.append(seg)
    return out


def pick_moments(words, max_clip_seconds=60, min_clip_seconds=8, max_clips=10,
                 video_duration=None, source=None, moment_pause=MOMENT_PAUSE,
                 scene_quiet=SCENE_QUIET, **_legacy):
    """Return [(start, end), ...] — whole moments that end on a real lull."""
    if not words:
        return _scene_or_even(source, video_duration, min_clip_seconds,
                              max_clip_seconds, max_clips, scene_quiet)

    end_of_speech = words[-1]["end"]
    hard_end = video_duration or end_of_speech
    speech_len = end_of_speech - words[0]["start"]
    target_len = min(max(speech_len / max(max_clips, 1), min_clip_seconds), max_clip_seconds)

    segs = _finalize(_moments_by_pause(words, moment_pause), max_clip_seconds)

    cands = []
    for seg in segs:
        s, e = seg[0]["start"], seg[-1]["end"]
        if e - s < min_clip_seconds:
            continue  # drop a too-short isolated blip
        text = " ".join(w["word"] for w in seg)
        cands.append({"start": s, "end": e, "score": _score_window(seg, text, target_len)})

    if not cands:
        return _scene_or_even(source, hard_end, min_clip_seconds,
                              max_clip_seconds, max_clips, scene_quiet)

    cands.sort(key=lambda c: c["score"], reverse=True)
    chosen = []
    for c in cands:
        if any(not (c["end"] <= x["start"] or c["start"] >= x["end"]) for x in chosen):
            continue
        chosen.append(c)
        if len(chosen) >= max_clips:
            break

    chosen.sort(key=lambda c: c["start"])
    out = [(max(c["start"] - 0.15, 0.0), min(c["end"] + 0.3, hard_end)) for c in chosen]
    print(f"[moments] picked {len(out)} clips (whole moments): "
          + ", ".join(f"{s:.0f}-{e:.0f}s" for s, e in out))
    return out


# ------------------------------ scene path -------------------------------- #

def _probe_duration(source):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(source)],
            capture_output=True, text=True, timeout=60,
        )
        return float(r.stdout.strip())
    except Exception:
        return None


def scene_cuts(source, threshold=0.4):
    """Timestamps (s) of visual scene changes via ffmpeg's scene detection."""
    cmd = ["ffmpeg", "-i", str(source), "-filter:v",
           f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception as e:
        print(f"[moments] scene detection failed: {str(e)[:100]}")
        return []
    return sorted({float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", r.stderr)})


def _scene_moments(cuts, duration, quiet_gap):
    """A moment = a run of scene activity; it ends where the footage stays calm
    (no scene change) for >= quiet_gap seconds (the action settled)."""
    pts = sorted({0.0, *[c for c in cuts if 0 < c < duration], float(duration)})
    segs, seg_start = [], 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        if b - a >= quiet_gap:  # a calm stretch → the moment ended at `a`
            if a - seg_start >= 0.1:
                segs.append((seg_start, a))
            seg_start = b
    if duration - seg_start >= 0.1:
        segs.append((seg_start, duration))
    return segs


def _scene_or_even(source, duration, min_len, max_len, max_clips, scene_quiet):
    if source:
        if not duration:
            duration = _probe_duration(source)
        cuts = scene_cuts(source)
        if cuts and duration:
            clips = []
            for s, e in _scene_moments(cuts, duration, scene_quiet):
                d = e - s
                if d < min_len:
                    continue                            # drop tiny blip (don't span a lull)
                if d > max_len:
                    n = ceil(d / max_len)
                    step = d / n
                    t = s
                    while t < e - 0.1 and len(clips) < max_clips:
                        clips.append((t, min(t + step, e)))
                        t += step
                else:
                    clips.append((s, e))
                if len(clips) >= max_clips:
                    break
            if clips:
                print(f"[moments] picked {len(clips)} clips (scene moments): "
                      + ", ".join(f"{s:.0f}-{e:.0f}s" for s, e in clips[:max_clips]))
                return clips[:max_clips]
    return _fallback_even(duration, min_len, max_len, max_clips)


def _fallback_even(duration, min_len, max_len, max_clips):
    """Last resort — split into up to max_clips evenly-spaced clips."""
    if not duration or duration < min_len:
        return [(0.0, duration or max_len)]
    target = min(max(duration / max_clips, min_len), max_len)
    out, t = [], 0.0
    while t + min_len <= duration and len(out) < max_clips:
        out.append((t, min(t + target, duration)))
        t += target
    return out or [(0.0, min(max_len, duration))]

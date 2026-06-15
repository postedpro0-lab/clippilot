"""Pick the best clippable segments from a transcript.

Free heuristic (no paid AI):
1. Split speech into natural units (sentences / pauses) so clips never start or
   end mid-action.
2. Build candidate clips from contiguous runs of those units, each between
   min_clip_seconds and max_clip_seconds long (variable length, <= 60s).
3. Score each candidate (speech density + hook words + numbers + clean ending).
4. Greedily keep the top non-overlapping clips, up to max_clips.
"""
import re

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


def _tokens(text):
    return _TOKEN_RE.findall(text.lower())


def _score_window(win_words, text, target_len):
    if not win_words:
        return 0.0
    duration = win_words[-1]["end"] - win_words[0]["start"]
    if duration <= 0:
        return 0.0

    wps = len(win_words) / duration
    density = min(wps / 3.0, 1.0)               # ~3 words/sec is lively

    toks = _tokens(text)
    hooks = len(set(toks) & HOOK_WORDS)
    hook_score = min(hooks / 6.0, 1.0)

    num_score = min(len(NUM_RE.findall(text)) / 3.0, 1.0)

    ends_clean = 1.0 if SENT_END_RE.search(text.strip()) else 0.0

    # prefer clips near the target length so ~max_clips of them tile the video
    # (keeps clips punchy instead of one long clip eating the whole timeline)
    length_score = max(0.0, 1.0 - abs(duration - target_len) / target_len)

    return (0.34 * density + 0.24 * hook_score + 0.08 * num_score
            + 0.14 * ends_clean + 0.20 * length_score)


def _units(words, pause_gap=0.45):
    """Split words into natural cut units: break after sentence-ending
    punctuation or a speech pause longer than `pause_gap` seconds."""
    units, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        ends_punct = bool(SENT_END_RE.search(w["word"].strip()))
        gap_next = (words[i + 1]["start"] - w["end"]) if i + 1 < len(words) else 1e9
        if ends_punct or gap_next >= pause_gap:
            units.append(cur)
            cur = []
    if cur:
        units.append(cur)
    return units


def pick_moments(words, max_clip_seconds=60, min_clip_seconds=8, max_clips=5,
                 video_duration=None, **_legacy):
    """Return list of (start, end) tuples for the best clips, at natural
    boundaries, each between min_clip_seconds and max_clip_seconds long."""
    if not words:
        return _fallback_even(video_duration, min_clip_seconds, max_clip_seconds, max_clips)

    units = _units(words)
    spans = [(u[0]["start"], u[-1]["end"], u) for u in units]
    end_of_speech = words[-1]["end"]
    hard_end = video_duration or end_of_speech

    # Aim for ~max_clips clips spread across the video: target each clip near
    # (speech length / max_clips), clamped to the allowed range.
    speech_len = end_of_speech - words[0]["start"]
    target_len = min(max(speech_len / max(max_clips, 1), min_clip_seconds), max_clip_seconds)

    # Build candidate clips = contiguous runs of whole units within length bounds.
    candidates = []
    n = len(spans)
    for i in range(n):
        for j in range(i, n):
            start = spans[i][0]
            end = spans[j][1]
            dur = end - start
            if dur > max_clip_seconds:
                break  # extending j only makes it longer
            if dur < min_clip_seconds:
                continue
            win = [w for k in range(i, j + 1) for w in spans[k][2]]
            text = " ".join(w["word"] for w in win)
            candidates.append({"start": start, "end": end,
                               "score": _score_window(win, text, target_len)})

    if not candidates:
        return _fallback_even(hard_end, min_clip_seconds, max_clip_seconds, max_clips)

    candidates.sort(key=lambda c: c["score"], reverse=True)

    chosen = []
    for c in candidates:
        overlaps = any(not (c["end"] <= x["start"] or c["start"] >= x["end"]) for x in chosen)
        if overlaps:
            continue
        chosen.append(c)
        if len(chosen) >= max_clips:
            break

    chosen.sort(key=lambda c: c["start"])
    out = []
    for c in chosen:
        # tiny lead-in / tail so we don't clip the first/last syllable
        s = max(c["start"] - 0.15, 0.0)
        e = min(c["end"] + 0.3, hard_end)
        out.append((s, e))

    print(f"[moments] picked {len(out)} clips: "
          + ", ".join(f"{s:.0f}-{e:.0f}s" for s, e in out))
    return out


def _fallback_even(duration, min_len, max_len, max_clips):
    """No usable speech — split the video into up to max_clips evenly-spaced
    clips. Without a transcript we can't find natural boundaries; this at least
    yields several clips instead of one. (For true action-aware cuts on silent
    footage, scene-change detection would be needed.)"""
    if not duration or duration < min_len:
        return [(0.0, duration or max_len)]
    target = min(max(duration / max_clips, min_len), max_len)
    out, t = [], 0.0
    while t + min_len <= duration and len(out) < max_clips:
        out.append((t, min(t + target, duration)))
        t += target
    return out or [(0.0, min(max_len, duration))]

"""Pick the most 'clippable' ~30s windows from a transcript.

Free heuristic (no paid AI): slide a window over the speech and score it by
- speech density (more talking, less dead air = better)
- hook words (questions, numbers, emotional/curiosity triggers)
- ending on a sentence boundary (clips that don't cut mid-word feel finished)
Then take the top N non-overlapping windows.
"""
import re

HOOK_WORDS = {
    "you", "your", "why", "how", "what", "secret", "never", "always", "best",
    "worst", "stop", "mistake", "money", "free", "now", "today", "first",
    "imagine", "crazy", "insane", "actually", "literally", "because", "but",
    "wait", "listen", "watch", "look", "here's", "this", "nobody", "everyone",
}
NUM_RE = re.compile(r"\b\d+\b")
SENT_END_RE = re.compile(r"[.!?]\s*$")


def _score_window(words_in_window, full_text):
    if not words_in_window:
        return 0.0
    duration = words_in_window[-1]["end"] - words_in_window[0]["start"]
    if duration <= 0:
        return 0.0

    wps = len(words_in_window) / duration            # words per second
    density = min(wps / 3.0, 1.0)                     # ~3 wps is lively speech

    text = full_text.lower()
    hooks = sum(1 for w in HOOK_WORDS if w in text)
    hook_score = min(hooks / 8.0, 1.0)

    numbers = len(NUM_RE.findall(full_text))
    num_score = min(numbers / 3.0, 1.0)

    ends_clean = 1.0 if SENT_END_RE.search(full_text.strip()) else 0.0

    return 0.45 * density + 0.30 * hook_score + 0.10 * num_score + 0.15 * ends_clean


def pick_moments(words, clip_seconds=30, max_clips=5, min_gap=15, video_duration=None):
    """Return list of (start, end) tuples for the best windows."""
    if not words:
        # No speech detected — fall back to evenly spaced cuts.
        return _fallback_even(video_duration, clip_seconds, max_clips)

    end_of_speech = words[-1]["end"]
    step = max(clip_seconds / 3.0, 5)  # slide in thirds of a clip
    candidates = []

    t = words[0]["start"]
    while t + clip_seconds <= end_of_speech + step:
        win = [w for w in words if t <= w["start"] < t + clip_seconds]
        text = " ".join(w["word"] for w in win)
        score = _score_window(win, text)
        candidates.append({"start": t, "end": t + clip_seconds, "score": score})
        t += step

    if not candidates:
        return _fallback_even(video_duration or end_of_speech, clip_seconds, max_clips)

    candidates.sort(key=lambda c: c["score"], reverse=True)

    chosen = []
    for c in candidates:
        if any(abs(c["start"] - x["start"]) < (clip_seconds + min_gap) for x in chosen):
            continue
        chosen.append(c)
        if len(chosen) >= max_clips:
            break

    chosen.sort(key=lambda c: c["start"])
    print(f"[moments] picked {len(chosen)} clips: "
          + ", ".join(f"{c['start']:.0f}-{c['end']:.0f}s({c['score']:.2f})" for c in chosen))
    return [(c["start"], c["end"]) for c in chosen]


def _fallback_even(duration, clip_seconds, max_clips):
    if not duration:
        return [(0, clip_seconds)]
    out, t = [], 0
    while t + clip_seconds <= duration and len(out) < max_clips:
        out.append((t, t + clip_seconds))
        t += clip_seconds
    return out or [(0, min(clip_seconds, duration))]

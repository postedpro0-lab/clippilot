"""Transcribe locally with faster-whisper. Returns word-level timestamps."""
from faster_whisper import WhisperModel

_model_cache = {}


def _get_model(name):
    if name not in _model_cache:
        # int8 on CPU = fast + low memory, works fine in GitHub Actions
        _model_cache[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _model_cache[name]


def transcribe(audio_or_video_path, model_name="base", language=""):
    """Return (segments, words).

    segments: list of {start, end, text}
    words:    list of {start, end, word}
    """
    model = _get_model(model_name)
    seg_iter, _info = model.transcribe(
        str(audio_or_video_path),
        language=language or None,
        word_timestamps=True,
        vad_filter=True,  # skip long silences
    )

    segments, words = [], []
    for seg in seg_iter:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        for w in (seg.words or []):
            words.append({"start": w.start, "end": w.end, "word": w.word.strip()})
    print(f"[transcribe] {len(segments)} segments, {len(words)} words")
    return segments, words

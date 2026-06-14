"""Turn a @handle / channel URL / raw UC id into a channel_id, and a clean
folder label. Used at runtime so config.yaml just lists channels."""
import re

import requests

_cache = {}


def channel_id(value):
    """Resolve a channels[] entry to a UC... channel_id."""
    value = value.strip()
    if value in _cache:
        return _cache[value]

    if value.startswith("UC") and len(value) == 24:
        _cache[value] = value
        return value

    if value.startswith("@"):
        url = f"https://www.youtube.com/{value}"
    elif value.startswith("http"):
        url = value
    else:
        url = f"https://www.youtube.com/@{value}"

    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    for pat in (r'"channelId":"(UC[0-9A-Za-z_-]{22})"',
                r'"externalId":"(UC[0-9A-Za-z_-]{22})"',
                r'channel/(UC[0-9A-Za-z_-]{22})'):
        m = re.search(pat, html)
        if m:
            _cache[value] = m.group(1)
            return m.group(1)
    raise RuntimeError(f"Could not resolve a channel_id for '{value}'. "
                       "Paste the raw UC... id in config.yaml instead.")


def label(value):
    """A filesystem-safe folder name for a channels[] entry."""
    v = value.strip()
    m = re.search(r"@([A-Za-z0-9_.-]+)", v)
    if m:
        v = m.group(1)
    elif v.startswith("UC"):
        pass
    else:
        v = re.sub(r"^https?://(www\.)?youtube\.com/", "", v).strip("/")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", v) or "channel"

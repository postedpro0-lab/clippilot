#!/usr/bin/env python3
"""Sanity-check the `channels:` list in config.yaml — resolves each entry to its
channel_id so you can confirm they're all valid before a real run.

Usage: python scripts/resolve_channel.py
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import resolve  # noqa: E402

cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
channels = cfg.get("channels") or []
if not channels:
    raise SystemExit("No channels listed in config.yaml under `channels:`")

print(f"Checking {len(channels)} channel(s)...\n")
ok = True
for entry in channels:
    try:
        cid = resolve.channel_id(entry)
        print(f"  ✅ {entry:<40} -> {cid}   (folder: {resolve.label(entry)})")
    except Exception as e:
        ok = False
        print(f"  ❌ {entry:<40} -> {e}")

print("\nAll good." if ok else "\nSome channels failed — fix them in config.yaml.")

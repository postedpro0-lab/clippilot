#!/bin/bash
# ClipPilot local runner — used by launchd. Ensures the PO-token provider is
# running, then runs the pipeline with the venv's Python.
set -u
cd /Users/wyatt/Desktop/ClipPilot

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"   # ffmpeg, node
LOG="/Users/wyatt/Desktop/ClipPilot/clippilot.log"

# Prevent two runs at once (they'd share work/ and delete each other's files).
# mkdir is atomic; the lock auto-clears when this script exits.
LOCKDIR="/tmp/clippilot.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "ClipPilot is already running — skipping this run." | tee -a "$LOG"
  exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

echo "===== $(date) : ClipPilot run starting =====" >> "$LOG"

# 1) Ensure the bgutil PO-token provider is up (beats YouTube SABR).
if ! curl -s http://127.0.0.1:4416/ping >/dev/null 2>&1; then
  echo "[run_local] starting PO-token provider..." >> "$LOG"
  (cd /Users/wyatt/Desktop/ClipPilot/.potprovider && nohup node build/main.js >> /Users/wyatt/Desktop/ClipPilot/potprovider.log 2>&1 &)
  # wait up to ~20s for it to come up
  for i in $(seq 1 20); do
    curl -s http://127.0.0.1:4416/ping >/dev/null 2>&1 && break
    sleep 1
  done
fi
curl -s http://127.0.0.1:4416/ping >> "$LOG" 2>&1; echo >> "$LOG"

# 2) Run the pipeline.
/Users/wyatt/Desktop/ClipPilot/.venv/bin/python -u run.py >> "$LOG" 2>&1
echo "===== $(date) : ClipPilot run finished (exit $?) =====" >> "$LOG"

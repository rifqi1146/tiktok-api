#!/usr/bin/env bash
# Launcher TikTok REST API
#   PORT=8099 ./run_api.sh
#   HEADLESS=1 ./run_api.sh      -> tanpa Xvfb (mode headless)
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${PORT:-8099}"
HOST="${HOST:-0.0.0.0}"
VENV="$DIR/.venv"

if [ ! -x "$VENV/bin/uvicorn" ]; then
  echo "[!] venv belum ada. Jalankan dulu:"
  echo "    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Engine butuh headed Chromium (Akamai menolak headless murni pada halaman SSR),
# jadi Xvfb dipakai untuk menyediakan X server virtual.
if [ "${HEADLESS:-0}" = "1" ]; then
  echo "[*] Launching TikTok REST API (headless) on http://$HOST:$PORT"
  exec "$VENV/bin/uvicorn" tiktok_api.app:app --host "$HOST" --port "$PORT" --log-level info
fi

if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "[!] xvfb-run tidak ditemukan. Install: apt-get install -y xvfb"
  echo "    atau jalankan dengan HEADLESS=1 ./run_api.sh (hasil scraping bisa lebih sering kena blokir)"
  exit 1
fi

echo "[*] Launching TikTok REST API on http://$HOST:$PORT"
exec xvfb-run -a -s "-screen 0 1440x900x24" \
  "$VENV/bin/uvicorn" tiktok_api.app:app --host "$HOST" --port "$PORT" --log-level info

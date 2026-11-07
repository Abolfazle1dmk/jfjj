#!/bin/sh
# ═══════════════════════════════════════════════════════════════════════════
#  Enzonic Deploy — "app folder" entrypoint  (Root directory = enzonic)
#
#  Enzonic cannot build Docker images yet and refuses the project while the
#  framework preset is Dockerfile:
#
#      "Dockerfile projects cannot be built yet … Set the root directory to
#       the app's folder or pick a framework preset in the project settings."
#
#  The repo root carries a Dockerfile for blitz.cloud / Render / Railway, and
#  that may be what the auto-detection keeps picking. This folder has no
#  Dockerfile, only what a Python source build needs (requirements.txt,
#  .python-version, Procfile, nixpacks.toml), so it is the "app's folder" the
#  error message talks about:
#
#      Settings → Root directory = enzonic      (Framework: Python)
#      Install: pip install -r requirements.txt
#      Start:   sh start.sh
#
#  Nothing is duplicated here: the requirements file points at the repo's own
#  requirements.txt, and this wrapper hands over to the repo's portable
#  entrypoint (start.sh → hostless-start.sh → railway-start.sh) one level up,
#  so the bot still runs the code from the checkout.
# ═══════════════════════════════════════════════════════════════════════════
set -eu

HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || HERE="."
APP_ROOT="$(cd "$HERE/.." 2>/dev/null && pwd)" || APP_ROOT=""

if [ -z "$APP_ROOT" ] || [ ! -f "$APP_ROOT/start.sh" ]; then
    echo "ENZONIC: the repository root is not next to this folder." >&2
    echo "ENZONIC: use Root directory = / (repo root) with Framework = Python," >&2
    echo "ENZONIC: or set Root directory = enzonic inside the full checkout." >&2
    exit 1
fi

# The platform owns PORT; the app folder only launches the real entrypoint.
exec sh "$APP_ROOT/start.sh" "$@"

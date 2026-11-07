#!/bin/sh
# ═══════════════════════════════════════════════════════════════════════════
#  Portable entrypoint for SOURCE builds (no Docker image).
#
#  Enzonic Deploy, the Hostless "Python build", a Render native Python service,
#  a Heroku/nixpacks builder and a bare VPS all do the same thing: they
#  `pip install -r requirements.txt` into a checkout of this repo and then run
#  exactly ONE command. That command is this file.
#
#      Build:  pip install -r requirements.txt
#      Start:  sh start.sh          (also declared in Procfile / nixpacks.toml)
#
#  Enzonic Deploy prints this when the project is left on the Dockerfile
#  preset (it cannot build images yet):
#
#      "Dockerfile projects cannot be built yet: Enzonic Deploy builds
#       Node.js, Bun, Python and Go apps from source."
#
#  Nothing in the code has to change for a source build — every script here is
#  already host-neutral. Use the Python preset and this file as the start
#  command.
#
#  This wrapper deliberately carries no logic of its own: hostless-start.sh
#  picks the code directory (the immutable /opt/jafj copy on a Docker build,
#  this checkout on a source build), picks a writable data directory,
#  marks the process as hosted (a bot service must never "finish"), and hands
#  over to railway-start.sh — the single supervisor. All this file adds is an
#  honest host label in /diag and /version.
# ═══════════════════════════════════════════════════════════════════════════
set -eu

HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || HERE="."

# The platform decides the port (PORT) and the working directory; never set
# either of them here. JAFJ_HOSTED=1 means "a clean exit still counts as a
# crash", because on a managed host a process that exits is a dead service.
export JAFJ_HOSTED="${JAFJ_HOSTED:-1}"
export JAFJ_HOST_LABEL="${JAFJ_HOST_LABEL:-source}"

exec sh "$HERE/hostless-start.sh" "$@"

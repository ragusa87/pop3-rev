#!/bin/bash
# Run a live-memory capture script (watch_camera.py, livemem.py, ...) inside the
# container as root, so it can read /proc/<pid>/mem of the wine process without
# the host sudo password prompt. The repo is bind-mounted at /work (see
# docker-compose.yml), so paths are relative to the repo root.
# Usage: scripts/docker/capture.sh scripts/watch_camera.py --scan-tribe
set -euo pipefail

exec docker compose exec -u root -w /work pop3 python3 "$@"

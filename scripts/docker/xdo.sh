#!/bin/bash
# Run an xdotool command against the container's virtual display.
# Usage: scripts/docker/xdo.sh key Return
#        scripts/docker/xdo.sh mousemove 512 384 click 1
set -euo pipefail

exec docker compose exec pop3 xdotool "$@"

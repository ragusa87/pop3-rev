#!/bin/bash
# Run scripts/watch_addr.py (GDB hardware write-watchpoint) inside the container as root, same
# reasoning as capture.sh: needs real ptrace/root, which the container gives for free instead of
# a host sudo password prompt. Requires gdb in the image (docker/Dockerfile).
# Usage: scripts/docker/watch_addr.sh tribe+0x2c [--seconds 300]
set -euo pipefail

exec docker compose exec -u root -w /work pop3 python3 scripts/watch_addr.py "$@"

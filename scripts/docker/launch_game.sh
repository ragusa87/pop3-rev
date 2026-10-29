#!/bin/bash
# Launch the game exe inside the running pop3 container (see docker-compose.yml).
# Usage: scripts/docker/launch_game.sh [path/to/EXE inside the wine prefix]
set -euo pipefail

DEFAULT_EXE="C:\\Program Files (x86)\\Bullfrog\\Populous - A l'aube de la création\\D3DPOPTB.EXE"
POP_EXE="${1:-$DEFAULT_EXE}"

# Reassert every run: ~/.wine is bind-mounted from the host, so a host-side
# wine session can change this shared prefix's registry between runs. Without
# the Desktop override, the game's ddraw wrapper's forced display-mode switch
# crashes it on startup (Xvfb has no matching real XRandR mode).
docker compose exec pop3 wine reg add "HKCU\Software\Wine\Drivers" /v Audio /t REG_SZ /d "" /f >/dev/null
docker compose exec pop3 wine reg add "HKCU\Software\Wine\Explorer" /v Desktop /d Default /f >/dev/null
docker compose exec pop3 wine reg add "HKCU\Software\Wine\Explorer\Desktops" /v Default /d "800x600" /f >/dev/null

# -allres: real equivalent of what ddraw__.dll patches into the binary at
# runtime (confirmed via `strings`: D3DPOPTB.EXE also takes NOGAMMA,
# FRAMERATEMOUSE, SCREENRES, LEVEL, NOCONFIG, NAME, HARDDRIVE, D3D_DEBUG).
exec docker compose exec -d pop3 wine "${POP_EXE}" -allres

#!/bin/bash
# Headless-automate: launch the 3D exe (D3DPOPTB.EXE) in the pop3 container and
# click/key through to level 1 being loaded and running.
#
# Resolution chain (see docker/entrypoint.sh for why): Xvfb virtual screen is
# 2256x1504x24; Wine's virtual-desktop window inside it is 800x600 at (0,0);
# the game's own window inside that is 640x480 at (0,0) - so game-relative
# pixel coordinates equal Xvfb-root coordinates throughout, no offset.
#
# Mouse clicks via xdotool do NOT reliably reach the game window in this setup
# (no X11 window manager is running in Xvfb, so the game never gets real
# foreground/input focus for its DirectInput mouse acquisition) - keyboard
# input works reliably instead, so this whole sequence is keyboard-driven:
#   1. Launch -> Bullfrog/EA splash -> main menu (~8-10s). "NOUVELLE PARTIE"
#      (New Game) is already the default-highlighted item, so Enter alone
#      selects it.
#   2. Enter -> an intro FMV plays (length varies run to run - sometimes just a
#      black frame, sometimes several seconds of an actual planets/zoom video;
#      cause not confirmed, maybe cold vs. warm codec/decoder state) -> Escape
#      skips it, landing on the level-select star map with level 1
#      ("01: L'AVENTURE COMMENCE") already the focused/default node.
#   3. Enter again confirms and loads level 1 - lands in-game within ~3s.
# D3DPOPTB.EXE recognises a few undocumented command-line switches (confirmed via
# `strings D3DPOPTB.EXE`: D3D_DEBUG, NOGAMMA, FRAMERATEMOUSE, ALLRES, SCREENRES,
# LEVEL, NOCONFIG, NAME, HARDDRIVE). -allres is the real equivalent of what the
# ddraw__.dll wrapper patches into the binary at runtime ("set ALLRES-equivalent
# bit at RVA ..." in ddraw_proxy.log) - pass it directly instead of relying only
# on that patch.
set -euo pipefail

docker compose exec pop3 wineserver -k >/dev/null 2>&1 || true
sleep 1

# Reassert every run, not just at container startup: ~/.wine is bind-mounted
# from the host, so a host-side wine session (different Desktop/Audio settings)
# can change this shared prefix's registry between runs.
docker compose exec pop3 wine reg add "HKCU\Software\Wine\Drivers" /v Audio /t REG_SZ /d "" /f >/dev/null
docker compose exec pop3 wine reg add "HKCU\Software\Wine\Explorer" /v Desktop /d Default /f >/dev/null
docker compose exec pop3 wine reg add "HKCU\Software\Wine\Explorer\Desktops" /v Default /d "800x600" /f >/dev/null

docker compose exec -d pop3 bash -c 'wine "C:\\Program Files (x86)\\Bullfrog\\Populous - A l'"'"'aube de la création\\D3DPOPTB.EXE" -allres'

sleep 10
docker compose exec pop3 xdotool key Return   # main menu -> "Nouvelle partie"
sleep 6                                       # intro FMV length varies run to run
docker compose exec pop3 xdotool key Escape   # skip it (no visible frames headless either way)
sleep 2
docker compose exec pop3 xdotool key Return   # level-select -> start level 1
sleep 3

echo "level 1 should now be loaded - connect a VNC viewer to localhost:5900 to confirm"

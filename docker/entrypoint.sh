#!/bin/bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY#:}"

Xvfb ":${DISPLAY_NUM}" -screen 0 2256x1504x24 &
for _ in $(seq 1 50); do
    [ -e "/tmp/.X11-unix/X${DISPLAY_NUM}" ] && break
    sleep 0.1
done

x11vnc -display ":${DISPLAY_NUM}" -forever -shared -nopw \
    -listen 0.0.0.0 -rfbport 5900 -bg -q -o /tmp/x11vnc.log

# Minimal window manager: without one, no window (the game included) ever gets
# real X input focus, so synthesized mouse clicks (xdotool, VNC) never reach
# the game's own DirectInput acquisition - keyboard works regardless, but
# clicks silently do nothing. openbox's default click-to-focus policy is
# enough; no further config needed.
openbox --sm-disable &
sleep 1

# Wine audio-disable and virtual-desktop registry settings are NOT set here:
# ~/.wine is bind-mounted from the host, so this prefix's registry is shared,
# mutable state that a host-side wine session can change between container
# runs. Scripts that actually launch the game (scripts/docker/*.sh) reassert
# those settings themselves right before every launch instead - see there for
# why they're needed (display-mode mismatch between the game's ddraw wrapper
# and Xvfb).

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec sleep infinity

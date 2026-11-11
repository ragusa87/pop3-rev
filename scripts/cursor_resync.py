#!/usr/bin/env python3
"""Resync D3DPOPTB.EXE's internal mouse cursor to the real X11 pointer.

The game reads its mouse via DirectInput in exclusive mode (relative deltas),
so a large pointer warp (xdotool mousemove, a fresh VNC connection's first
event) desyncs the game's internal cursor from the real X11 pointer. Instead
of restarting the game, write the real pointer's window-local position into
the game's cursor-position globals (found by live scan 2026-11-11, see
docs/cheat.md "cursor drift" sections):

  0xd0597c  DirectInput-side accumulated position (likely the source)
  0xa69030, 0xa69070, 0x749c90, 0x749df4  game-side copies (same value)

Run INSIDE the container as root (needs ptrace + DISPLAY):
  docker compose exec -u root pop3 python3 /repo/scripts/cursor_resync.py
Keep the mouse still while it runs. Pass x y window-local coords explicitly
to skip the xdotool query:  cursor_resync.py 320 240
"""
import os, re, struct, subprocess, sys

ADDRS = (0xD0597C, 0xA69030, 0xA69070, 0x749C90, 0x749DF4)
WIN_NAME = "Populous, The Beginning"


def game_pid():
    out = subprocess.run(["pgrep", "-f", r"D3DPOPTB\.EXE"], capture_output=True, text=True)
    pids = [int(p) for p in out.stdout.split()]
    for pid in pids:
        try:
            with open(f"/proc/{pid}/stat") as f:
                if "Z" not in f.read().split(")")[1].split()[0]:
                    return pid
        except OSError:
            pass
    sys.exit("no live D3DPOPTB.EXE process")


def xdotool(*args):
    env = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":99"))
    return subprocess.run(["xdotool", *args], capture_output=True, text=True, env=env).stdout


def pointer_local():
    loc = xdotool("getmouselocation")
    mx, my = (int(m) for m in re.match(r"x:(\d+) y:(\d+)", loc).groups())
    wid = xdotool("search", "--name", WIN_NAME).split()[0]
    geo = xdotool("getwindowgeometry", wid)
    wx, wy = (int(m) for m in re.search(r"Position: (\d+),(\d+)", geo).groups())
    return mx - wx, my - wy


def main():
    if len(sys.argv) == 3:
        x, y = int(sys.argv[1]), int(sys.argv[2])
    else:
        x, y = pointer_local()
    if not (0 <= x <= 639 and 0 <= y <= 479):
        sys.exit(f"pointer ({x},{y}) is outside the 640x480 window - move it inside first")
    pid = game_pid()
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        for addr in ADDRS:
            mem.seek(addr)
            mem.write(struct.pack("<II", x, y))
    print(f"pid {pid}: cursor resynced to window-local ({x},{y})")


if __name__ == "__main__":
    main()

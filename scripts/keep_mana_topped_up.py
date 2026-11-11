"""Testing aid, not a trace tool: keeps every spell known, unblocked and well-fed with mana so a
live session can cast anything on demand without the UI's own charge-up grind getting in the way.
Re-applies every ~2s because `struct_56B` (learned/blocked bitmasks) can get stomped by a per-tribe
resync the game runs on its own (docs/cheat.md "Open problems" - not root-caused, this is the
documented pragmatic workaround: a continuously-running clear-loop).

sudo python3 keep_mana_topped_up.py   (or scripts/docker/capture.sh scripts/keep_mana_topped_up.py)
"""
import os
import struct
import sys
import time

TRIBE_BASE, INCOMING_OFF, PLAYER_TRIBE_ADDR = 0x89D1C8, 0x955, 0x89C6F0
STRUCT56B_BASE, LEARNED_OFF, BLOCKED_OFF = 0x96070A, 0x0, 0x10
INCOMING_TARGET = 50_000_000


def find_game():
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().lower()
        except OSError:
            continue
        if not cmd.startswith(b"c:\\"):
            continue
        if b"d3dpoptb.exe" in cmd:
            return int(pid), (lambda addr: addr)
        if b"poptb.exe" in cmd:
            sys.path.insert(0, "/home/laurent/compile/pop3-rev/.claude/skills/original-game-spec/scripts")
            from addrmap import AddrMap
            return int(pid), AddrMap.load().to_poptb
    return None, None


def main():
    pid, translate = find_game()
    if pid is None:
        print("game not running", file=sys.stderr)
        return
    print(f"keeping mana/spells topped up for pid {pid} - Ctrl+C to stop", flush=True)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        while True:
            mem.seek(translate(PLAYER_TRIBE_ADDR))
            tribe = mem.read(1)[0]

            addr = translate(TRIBE_BASE + tribe * 0xC65 + INCOMING_OFF)
            mem.seek(addr)
            incoming = struct.unpack("<I", mem.read(4))[0]
            if incoming < INCOMING_TARGET // 2:
                mem.seek(addr)
                mem.write(struct.pack("<I", INCOMING_TARGET))

            base = STRUCT56B_BASE + tribe * 0x38
            mem.seek(translate(base + LEARNED_OFF))
            mem.write(struct.pack("<I", 0xFFFFFFFF))
            mem.seek(translate(base + BLOCKED_OFF))
            mem.write(struct.pack("<I", 0))

            time.sleep(2)


if __name__ == "__main__":
    main()

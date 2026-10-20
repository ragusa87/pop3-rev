"""Per turn: people in preach-conversion states (3, 23, 24), their target/timer/tribe.

usage: preachwatch.py
"""
import struct
import sys
import time

sys.path.insert(0, "/home/laurent/compile/pop3-rev/.claude/skills/original-game-spec/scripts")
from livemem import find_game

TURN = 0x89D188
UNIT_PTRS = 0x890390
UNIT_POOL, UNIT_SIZE, UNIT_COUNT = 0x8E0428, 0xB3, 2000
STATES = {3: "struck", 23: "converting", 24: "state24"}


def rd(mem, addr, fmt):
    mem.seek(addr)
    size = struct.calcsize(fmt)
    data = mem.read(size)
    if len(data) < size:
        raise OSError("short read")
    return struct.unpack(fmt, data)


def units(mem):
    mem.seek(UNIT_POOL)
    pool = mem.read(UNIT_SIZE * UNIT_COUNT)
    if len(pool) < UNIT_SIZE * UNIT_COUNT:
        raise OSError("short read")
    out = {}
    for i in range(UNIT_COUNT):
        r = pool[i * UNIT_SIZE:(i + 1) * UNIT_SIZE]
        (flags,) = struct.unpack_from("<I", r, 0xC)
        if r[0x2A] and not flags & 1:
            out[struct.unpack_from("<H", r, 0x24)[0]] = r
    return out


def describe(uid, r):
    (target,) = struct.unpack_from("<H", r, 0x89)
    (timer,) = struct.unpack_from("<h", r, 0x70)
    x, z = struct.unpack_from("<2H", r, 0x3D)
    return (f"#{uid} t{r[0x2B]} tr{r[0x2F]} st{r[0x2C]}/{STATES.get(r[0x2C], '?')} sub{r[0x2D]}"
            f" timer{timer} ({x},{z}) -> target #{target}")


def main():
    global TURN, UNIT_PTRS, UNIT_POOL
    pid, translate = find_game()
    if not pid:
        sys.exit("neither D3DPOPTB.EXE nor POPTB.EXE is running")
    TURN, UNIT_PTRS, UNIT_POOL = map(translate, (TURN, UNIT_PTRS, UNIT_POOL))
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        try:
            watch(mem)
        except OSError:
            sys.exit("the game closed")


def watch(mem):
    last_turn, before = None, {}
    while True:
        (turn,) = rd(mem, TURN, "<I")
        if turn != last_turn:
            last_turn = turn
            now = units(mem)
            lines = []
            for uid, r in sorted(now.items()):
                if r[0x2C] in STATES:
                    lines.append(describe(uid, r))
            for uid in before:
                if uid not in now and before[uid][0x2C] in STATES:
                    lines.append(f"#{uid} GONE (was {STATES.get(before[uid][0x2C], '?')})")
            before = now
            if lines:
                print(f"turn {turn}", *lines, sep="\n  ", flush=True)
        time.sleep(0.01)


if __name__ == "__main__":
    main()

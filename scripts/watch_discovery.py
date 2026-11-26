"""Live, read-only log of every discovery (class 6 type 2, the reward icon on a vault or totem) and its glow
(class 6 type 8): position, height against the building under it, drawable, animation clock and the pickup
fields (+0x74 reward, +0x78 glow id, +0x7A countdown, +0x7C kind, +0x7E tribe, +0x7F hide delay), on change.

Usage (inside the docker rig):
  scripts/docker/capture.sh scripts/watch_discovery.py [--turns N]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
THING_TABLE = 0x890390
THING_COUNT = 0x1000


def read(mem, ptr, n):
    mem.seek(ptr)
    return mem.read(n)


def main():
    max_turns = 20000
    args = sys.argv[1:]
    if "--turns" in args:
        max_turns = int(args[args.index("--turns") + 1])
    pid = None
    while not pid:
        pid, translate = find_game()
        if not pid:
            time.sleep(0.2)
    print(f"attached to pid {pid}", flush=True)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        last, first, prev = None, None, {}
        while True:
            turn = struct.unpack("<I", read(mem, translate(TURN), 4))[0]
            if turn == last:
                time.sleep(0.01)
                continue
            last = turn
            first = turn if first is None else first
            ptrs = struct.unpack(f"<{THING_COUNT}I", read(mem, translate(THING_TABLE), THING_COUNT * 4))
            now = {}
            for idx, ptr in enumerate(ptrs):
                if not ptr:
                    continue
                try:
                    b = read(mem, ptr, 0x84)
                except OSError:
                    continue
                cls, typ, st, sub, cnt, tribe = struct.unpack_from("<5Bb", b, 0x2A)
                if (cls, typ) not in ((6, 2), (6, 8), (2, 18)):
                    continue
                x, z, h = struct.unpack_from("<HHh", b, 0x3D)
                model, flags35, clock = struct.unpack_from("<HHH", b, 0x33)
                dclass = b[0x3A]
                rec = (cls, typ, st, sub, tribe, x, z, h, model, flags35, dclass)
                if (cls, typ) == (6, 2):
                    reward, glow, count = struct.unpack_from("<IHh", b, 0x74)
                    rec += (reward, glow, count, b[0x7C], b[0x7E], b[0x7F], b[0x80])
                now[idx] = rec
                if prev.get(idx) != rec:
                    print(f"t{turn} #{idx} {rec}", flush=True)
            for idx in prev:
                if idx not in now:
                    print(f"t{turn} #{idx} gone", flush=True)
            prev = now
            if turn - first >= max_turns:
                break


if __name__ == "__main__":
    main()

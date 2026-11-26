"""Live, read-only log of every Convert spell effect (class 7 type 0x49): its life counter (+0x6C) each turn,
the sparkles (7/0x3C) born while one is alive (offset from the effect's cell centre, height vs. the effect, life),
and every person within 4 cells of it (wildmen's state/sub-state, disappearances, new braves).

Usage (inside the docker rig):
  scripts/docker/capture.sh scripts/watch_convert.py [--turns N]
"""
import math
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
THING_TABLE = 0x890390
THING_COUNT = 0x1000
NEAR = 4 * 512


def wrap(d):
    d &= 0xFFFF
    return d - 0x10000 if d >= 0x8000 else d


def scan(mem, ptrs):
    out = {}
    for idx, ptr in enumerate(ptrs):
        if not ptr:
            continue
        try:
            mem.seek(ptr + 0x2A)
            b = mem.read(0x6E - 0x2A)
        except OSError:
            continue
        cls, typ, st, sub, cnt, tribe = struct.unpack_from("<4BBb", b, 0)
        x, z, h = struct.unpack_from("<HHh", b, 0x3D - 0x2A)
        life = struct.unpack_from("<h", b, 0x6C - 0x2A)[0]
        out[idx] = (cls, typ, st, sub, cnt, tribe, x, z, h, life)
    return out


def main():
    max_turns = 20000
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--turns":
            max_turns = int(next(it))
    pid = None
    while not pid:
        pid, translate = find_game()
        if not pid:
            time.sleep(0.2)
    print(f"attached to pid {pid}", flush=True)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        last, first, prev, effects = None, None, {}, {}
        while True:
            mem.seek(translate(TURN))
            turn = struct.unpack("<I", mem.read(4))[0]
            if turn == last:
                time.sleep(0.01)
                continue
            last = turn
            first = turn if first is None else first
            mem.seek(translate(THING_TABLE))
            ptrs = struct.unpack(f"<{THING_COUNT}I", mem.read(THING_COUNT * 4))
            now = scan(mem, ptrs)
            for idx, r in now.items():
                if r[0] == 7 and r[1] == 0x49:
                    if idx not in effects:
                        print(f"t{turn} CONVERT #{idx} born tribe {r[5]} pos {r[6]:#06x},{r[7]:#06x} h {r[8]} "
                              f"state {r[2]} life {r[9]} counter {r[4]}", flush=True)
                    effects[idx] = r
            for idx in [i for i in effects if i not in now or now[i][:2] != (7, 0x49)]:
                print(f"t{turn} CONVERT #{idx} gone", flush=True)
                del effects[idx]
            for idx, r in effects.items():
                cx, cz = (r[6] & 0xFE00) + 0x100, (r[7] & 0xFE00) + 0x100
                print(f"t{turn} CONVERT #{idx} life {r[9]} counter {r[4]} state {r[2]}", flush=True)
                alive = [q for q in now.values() if q[0] == 7 and q[1] == 0x3C]
                print(f"   sparkles alive {len(alive)}", flush=True)
                for j, q in now.items():
                    p = prev.get(j)
                    if q[0] == 7 and q[1] == 0x3C and (p is None or p[:2] != q[:2] or p[6:8] != q[6:8]):
                        dx, dz = wrap(q[6] - cx), wrap(q[7] - cz)
                        print(f"   sparkle #{j} born d={math.hypot(dx, dz):.0f} ({dx},{dz}) dh={q[8] - r[8]} "
                              f"life {q[9]} state {q[2]}", flush=True)
                    if q[0] == 1:
                        dx, dz = wrap(q[6] - r[6]), wrap(q[7] - r[7])
                        if abs(dx) > NEAR or abs(dz) > NEAR:
                            continue
                        p = prev.get(j)
                        if p is None or p[:4] != q[:4] or (q[1] == 1 and (p[6], p[7]) != (q[6], q[7])):
                            print(f"   person #{j} type {q[1]} tribe {q[5]} state {q[2]}/{q[3]} cells "
                                  f"({dx / 512:+.2f},{dz / 512:+.2f}) {'NEW' if p is None else ''}", flush=True)
                for j, p in prev.items():
                    if p[0] == 1 and p[1] == 1 and j not in now:
                        dx, dz = wrap(p[6] - r[6]), wrap(p[7] - r[7])
                        if abs(dx) <= NEAR and abs(dz) <= NEAR:
                            print(f"   wildman #{j} GONE at cells ({dx / 512:+.2f},{dz / 512:+.2f})", flush=True)
            prev = now
            if turn - first >= max_turns:
                break


if __name__ == "__main__":
    main()

"""Testing aid: wait for a fresh Whirlwind (7/0x14, sub-state 0), move it and its homing point onto the nearest
sea cell, and point the local camera there. Run in the container as root."""
import os
import struct
import time

POOL, STRIDE, COUNT = 0x8E0428, 0xB3, 2000
CELLS, TERRAIN = 0x8A03F0, 0x5AA328
TRIBES, TSTRIDE, PLAYER = 0x89D1C8, 0xC65, 0x89C6F0


def pid():
    for p in filter(str.isdigit, os.listdir("/proc")):
        try:
            c = open(f"/proc/{p}/cmdline", "rb").read().lower()
            if c.startswith(b"c:\\") and b"d3dpoptb.exe" in c:
                return int(p)
        except OSError:
            pass


mem = open(f"/proc/{pid()}/mem", "r+b", buffering=0)


def rd(a, n):
    mem.seek(a)
    return mem.read(n)


def wr(a, b):
    mem.seek(a)
    mem.write(b)


cells = rd(CELLS, 128 * 128 * 16)
terrain = rd(TERRAIN, 16 * 14)


def sea(cx, cz):
    nib = cells[((cz % 128) * 128 + cx % 128) * 16] & 0xF
    return terrain[nib * 14] & 2


seen = set()
while True:
    pool = rd(POOL, STRIDE * COUNT)
    for i in range(COUNT):
        r = pool[i * STRIDE:(i + 1) * STRIDE]
        uid = struct.unpack_from("<H", r, 0x24)[0]
        if r[0x2A] == 7 and r[0x2B] == 0x14 and r[0x2D] == 0 and uid not in seen:
            seen.add(uid)
            x, z = struct.unpack_from("<HH", r, 0x3D)
            cx, cz = x >> 9, z >> 9
            best = min(((dx * dx + dz * dz, cx + dx, cz + dz) for dx in range(-30, 31) for dz in range(-30, 31)
                        if sea(cx + dx, cz + dz) and all(sea(cx + dx + a, cz + dz + b)
                                                         for a in (-1, 0, 1) for b in (-1, 0, 1))), default=None)
            if not best:
                print("no sea nearby", flush=True)
                continue
            _, sx, sz = best
            nx, nz = ((sx % 128) * 2 + 1) * 256, ((sz % 128) * 2 + 1) * 256
            a = POOL + i * STRIDE
            wr(a + 0x3D, struct.pack("<HH", nx, nz))
            wr(a + 0x4F, struct.pack("<HH", nx, nz))
            t = TRIBES + rd(PLAYER, 1)[0] * TSTRIDE
            wr(t + 0x24, struct.pack("<HH", nx, nz))
            print(f"moved whirlwind {uid} from cell ({cx},{cz}) to sea cell ({sx % 128},{sz % 128}) = ({nx},{nz})",
                  flush=True)
    time.sleep(0.02)

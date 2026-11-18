"""Live, read-only per-turn dump of every Whirlwind (effect 7/0x14) in play, its 16-segment funnel chain
(7/0x29, linked through +0x74), the people it lifts (person state 24), the dust it drops (7/0x2B), the
branches it tears off trees (7/0x39) and the wood piles it carries (scenery 5/0xB with +0x91 set).

Settles what the static trace of process_whirlwind (0x50F490) / its init (0x50F270) leaves open: the
segments' height scale +0x6A (never written by the spawner), the tint colours behind colour classes
-2/-1/3/4/5, and the real timings.

Usage: start D3DPOPTB.EXE (or POPTB.EXE) in a level, then
  sudo python3 scripts/watch_whirlwind.py [--every SECONDS] > ww.log
and cast Whirlwind near some people, trees and a wood pile, ideally with part of its path over sea.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills",
                                "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
POOL = 0x8E0428
STRIDE = 0xB3
COUNT = 2000
THING_TABLE = 0x890390
PALETTE_PTR = 0x87EFF8
ALPHA = 0x87F000
TINT = 0x5DA0E0


def u8(r, o):
    return r[o]


def s8(r, o):
    return struct.unpack_from("<b", r, o)[0]


def u16(r, o):
    return struct.unpack_from("<H", r, o)[0]


def s16(r, o):
    return struct.unpack_from("<h", r, o)[0]


class Mem:
    def __init__(self, f, translate):
        self.f, self.t = f, translate

    def raw(self, addr, n, live=False):
        self.f.seek(addr if live else self.t(addr))
        return self.f.read(n)

    def word(self, addr, fmt="<I", live=False):
        return struct.unpack(fmt, self.raw(addr, struct.calcsize(fmt), live))[0]


def colours(mem):
    pal = mem.word(PALETTE_PTR)
    out = []
    for c in (-2, -1, 3, 4, 5):
        idx = mem.raw(mem.t(ALPHA) + c * 0x1000 + 0x2F82, 1, live=True)[0]
        rgb = mem.raw(pal + idx * 4, 4, live=True)
        out.append(f"c{c}:idx{idx}=#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
    return f"palette_ptr={pal:#x} " + " ".join(out)


def pos(r):
    return u16(r, 0x3D), u16(r, 0x3F), s16(r, 0x41)


def main():
    every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 0.01
    pid, translate = None, None
    while not pid:
        pid, translate = find_game()
        if not pid:
            time.sleep(1)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as f:
        mem = Mem(f, translate)
        print(colours(mem), flush=True)
        pool_live = translate(POOL)
        last = None
        while True:
            turn = mem.word(TURN)
            if turn == last:
                time.sleep(every)
                continue
            last = turn
            pool = mem.raw(pool_live, STRIDE * COUNT, live=True)
            recs = [pool[i * STRIDE:(i + 1) * STRIDE] for i in range(COUNT)]
            ww = [r for r in recs if r[0x2A] == 7 and r[0x2B] == 0x14]
            if not ww:
                continue
            print(f"turn {turn}  tint_now={mem.word(TINT):06x}", flush=True)
            for r in ww:
                x, z, y = pos(r)
                print(f"  WW id={u16(r, 0x24)} st={r[0x2C]} sub={r[0x2D]} t72={s16(r, 0x72)} t61={s16(r, 0x61)} "
                      f"t76={s16(r, 0x76)} head={u16(r, 0x5D)} speed={s16(r, 0x5F)} pos=({x},{z},{y}) "
                      f"target=({u16(r, 0x4F)},{u16(r, 0x51)}) origin=({u16(r, 0x57)},{u16(r, 0x59)}) "
                      f"7b={r[0x7B]} 7c={r[0x7C]}")
                link_id, k = u16(r, 0x74), 0
                while link_id and k < 20:
                    ptr = mem.word(THING_TABLE + link_id * 4)
                    lr = mem.raw(ptr, STRIDE, live=True)
                    lx, lz, ly = pos(lr)
                    print(f"    seg{k} id={link_id} d=({lx - x},{lz - z}) h={ly - y} col={s8(lr, 0x3C)} "
                          f"w68={s16(lr, 0x68)} h6a={s16(lr, 0x6A)} spr={s16(lr, 0x33)} cls={lr[0x3A]} "
                          f"st={lr[0x2C]} f10={struct.unpack_from('<I', lr, 0x10)[0]:08x}")
                    link_id, k = u16(lr, 0x74), k + 1
            for r in recs:
                c, t, st = r[0x2A], r[0x2B], r[0x2C]
                if c == 1 and st == 24:
                    print(f"  LIFT id={u16(r, 0x24)} type={t} n={r[0x2D]} holder={u16(r, 0x89)} pos={pos(r)} "
                          f"obj={s16(r, 0x33)} f0c={struct.unpack_from('<I', r, 0xC)[0]:08x}")
                elif c == 7 and t == 0x2B:
                    print(f"  DUST id={u16(r, 0x24)} pos={pos(r)} col={s8(r, 0x3C)} life={s16(r, 0x6C)} "
                          f"spr={s16(r, 0x33)}")
                elif c == 7 and t == 0x39:
                    print(f"  BRANCH id={u16(r, 0x24)} n={r[0x2D]} pos={pos(r)} holder={u16(r, 0x72)}")
                elif c == 5 and t == 0xB and u16(r, 0x91):
                    print(f"  PILE id={u16(r, 0x24)} n={r[0x2D]} st={st} pos={pos(r)} holder={u16(r, 0x91)}")


if __name__ == "__main__":
    main()

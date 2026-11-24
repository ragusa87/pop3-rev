"""Live, read-only, turn-synced log of a level's opening Reincarnation Centre build: the 8 pillars
(tribe+0xA0D), the ground-flatten busy bit (tribe+0x93D bit 0), the camera (flyby) fields, every
class-7 effect appearing/disappearing anywhere, and every person near the RC anchor changing
type (wildman 1 -> brave 2) or state.

Usage (inside the docker rig):
  scripts/docker/capture.sh scripts/watch_rc_intro.py [--every S] [--radius UNITS] [--turns N]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
PLAYER_TRIBE = 0x89C6F0
TRIBE_BASE = 0x89D1C8
TRIBE_STRIDE = 0xC65
PILLAR_ARR_OFF = 0xA0D
RC_FLAGS_OFF = 0x93D
RC_ANCHOR_OFF = 0x911
CAM_FOCUS_OFF = 0x24
CAM_YAW_OFF = 0x32
EVENT_CLOCK = 0x969BE0
THING_TABLE = 0x890390
THING_COUNT = 0x1000


def rd(mem, addr, fmt):
    mem.seek(addr)
    return struct.unpack(fmt, mem.read(struct.calcsize(fmt)))[0]


def wrap_delta(a, b):
    d = (a - b) & 0xFFFF
    return d - 0x10000 if d >= 0x8000 else d


def read_thing(mem, ptr):
    mem.seek(ptr + 0x2A)
    cls, typ, st, st2, _cc, tribe = struct.unpack("<6B", mem.read(6))
    mem.seek(ptr + 0x3D)
    x, z, y = struct.unpack("<HHh", mem.read(6))
    return cls, typ, st, st2, tribe, x, z, y


def main():
    every, radius, max_turns = 0.02, 2560, 900
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--every":
            every = float(next(it))
        elif a == "--radius":
            radius = int(next(it))
        elif a == "--turns":
            max_turns = int(next(it))

    pid = None
    while not pid:
        pid, translate = find_game()
        if not pid:
            time.sleep(0.2)
    print(f"attached to pid {pid}", flush=True)

    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        last_turn = None
        last_hdr = None
        effects = {}
        people = {}
        while True:
            turn = rd(mem, translate(TURN), "<I")
            if turn == last_turn:
                time.sleep(every)
                continue
            last_turn = turn
            tribe = TRIBE_BASE + rd(mem, translate(PLAYER_TRIBE), "<B") * TRIBE_STRIDE
            rc = rd(mem, translate(tribe + RC_FLAGS_OFF), "<I")
            ax = rd(mem, translate(tribe + RC_ANCHOR_OFF), "<H")
            az = rd(mem, translate(tribe + RC_ANCHOR_OFF + 2), "<H")
            fx = rd(mem, translate(tribe + CAM_FOCUS_OFF), "<H")
            fz = rd(mem, translate(tribe + CAM_FOCUS_OFF + 2), "<H")
            yaw = rd(mem, translate(tribe + CAM_YAW_OFF), "<H")
            clock = rd(mem, translate(EVENT_CLOCK), "<H")
            pillars = []
            for i in range(8):
                wid = rd(mem, translate(tribe + PILLAR_ARR_OFF + i * 2), "<H")
                ptr = rd(mem, translate(THING_TABLE) + wid * 4, "<I") if wid else 0
                if ptr:
                    _c, _t, st, _s2, _tr, _x, _z, y = read_thing(mem, ptr)
                    pillars.append(f"{wid}:{st}:{y}")
                else:
                    pillars.append("-")
            hdr = (f"rc=0x{rc:x} anchor=({ax},{az}) cam=({fx},{fz}) yaw={yaw} evclock={clock} "
                   f"pillars={pillars}")
            if hdr != last_hdr:
                print(f"T{turn} {hdr}", flush=True)
                last_hdr = hdr

            mem.seek(translate(THING_TABLE))
            ptrs = struct.unpack(f"<{THING_COUNT}I", mem.read(4 * THING_COUNT))
            seen_e, seen_p = set(), set()
            for wid, ptr in enumerate(ptrs):
                if not ptr:
                    continue
                try:
                    cls, typ, st, st2, tr, x, z, y = read_thing(mem, ptr)
                except OSError:
                    continue
                dx, dz = wrap_delta(x, ax), wrap_delta(z, az)
                if cls == 7:
                    seen_e.add(wid)
                    key = (typ, st)
                    if wid not in effects:
                        print(f"T{turn} +eff id={wid} type=0x{typ:x} state={st} tribe={tr} "
                              f"pos=({x},{z},{y}) rel=({dx},{dz})", flush=True)
                    elif effects[wid] != key:
                        print(f"T{turn} ~eff id={wid} type=0x{typ:x} state={st}", flush=True)
                    effects[wid] = key
                elif cls == 1 and abs(dx) <= radius and abs(dz) <= radius:
                    seen_p.add(wid)
                    key = (typ, st, st2, tr)
                    if people.get(wid) != key:
                        print(f"T{turn} person id={wid} type={typ} state={st}/{st2} tribe={tr} "
                              f"rel=({dx},{dz},{y}) was={people.get(wid)}", flush=True)
                    people[wid] = key
            for wid in set(effects) - seen_e:
                print(f"T{turn} -eff id={wid} type=0x{effects.pop(wid)[0]:x}", flush=True)
            for wid in set(people) - seen_p:
                print(f"T{turn} person-gone id={wid} was={people.pop(wid)}", flush=True)
            if turn >= max_turns:
                return


if __name__ == "__main__":
    main()

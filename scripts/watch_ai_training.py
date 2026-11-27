"""Live, read-only log of computer-tribe unit production and script state, turn by turn.

Per turn: every person born/removed or changing type (training), counts by tribe and person type on change,
the first 64 script variables of each loaded script slot on change, and every 64 turns each tribe's mana
bank and a census line. Red's person-state changes are logged too (to see an attack muster/march).

Usage (inside the docker rig, start it before the level loads):
  scripts/docker/capture.sh scripts/watch_ai_training.py [--turns N] [--states TRIBE]
"""
import collections
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
THING_TABLE = 0x890390
THING_COUNT = 0x1000
TRIBE_BASE, TRIBE_SIZE, BANK = 0x89D1C8, 0xC65, 0x94D
SCRIPT_SLOTS, SCRIPT_SIZE, VARS_OFF, NVARS = 0x95F7B2, 12552, 0x1000, 64
TYPES = {1: "wild", 2: "brave", 3: "warrior", 4: "preacher", 5: "spy", 6: "fw", 7: "shaman", 8: "angel"}


def rd(mem, addr, fmt):
    mem.seek(addr)
    return struct.unpack(fmt, mem.read(struct.calcsize(fmt)))


def scan(mem, ptrs):
    out = {}
    for idx, ptr in enumerate(ptrs):
        if not ptr:
            continue
        try:
            cls, typ, st, st2, _, tribe = rd(mem, ptr + 0x2A, "<6B")
            x, z = rd(mem, ptr + 0x3D, "<HH")
        except OSError:
            continue
        if cls == 1:
            out[idx] = (tribe, typ, st, st2, x, z)
    return out


def census(units):
    c = collections.Counter((t, typ) for t, typ, *_ in units.values())
    return {t: {TYPES.get(k, k): n for (tt, k), n in sorted(c.items()) if tt == t} for t in sorted({t for t, _ in c})}


def main():
    max_turns, state_tribes = 10**9, {1}
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--turns":
            max_turns = int(next(it))
        elif a == "--states":
            state_tribes = {int(x) for x in next(it).split(",")}

    pid = None
    while not pid:
        pid, translate = find_game()
        if not pid:
            time.sleep(0.2)
    print(f"attached to pid {pid}", flush=True)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        last_turn, first_turn, prev, prev_census, prev_vars = None, None, {}, None, {}
        while True:
            turn = rd(mem, translate(TURN), "<I")[0]
            if turn == last_turn:
                time.sleep(0.005)
                continue
            if last_turn is not None and turn < last_turn:
                print(f"turn counter went back {last_turn} -> {turn}: new level?", flush=True)
                prev, prev_census, prev_vars = {}, None, {}
            last_turn = turn
            first_turn = first_turn if first_turn is not None else turn
            ptrs = rd(mem, translate(THING_TABLE), f"<{THING_COUNT}I")
            now = scan(mem, ptrs)
            for idx, (tribe, typ, st, st2, x, z) in now.items():
                old = prev.get(idx)
                if old is None:
                    if prev:
                        print(f"t{turn} + #{idx} tribe {tribe} {TYPES.get(typ, typ)} state {st}/{st2} at ({x},{z})", flush=True)
                elif old[1] != typ or old[0] != tribe:
                    print(f"t{turn} * #{idx} tribe {old[0]}->{tribe} {TYPES.get(old[1], old[1])}->{TYPES.get(typ, typ)} state {st}/{st2} at ({x},{z})", flush=True)
                elif tribe in state_tribes and typ != 1 and (old[2], old[3]) != (st, st2):
                    print(f"t{turn} s #{idx} tribe {tribe} {TYPES.get(typ, typ)} state {old[2]}/{old[3]} -> {st}/{st2} at ({x},{z})", flush=True)
            for idx, old in prev.items():
                if idx not in now:
                    print(f"t{turn} - #{idx} tribe {old[0]} {TYPES.get(old[1], old[1])} state {old[2]}/{old[3]} at ({old[4]},{old[5]})", flush=True)
            prev = now
            cen = census(now)
            if cen != prev_census:
                print(f"t{turn} census {cen}", flush=True)
                prev_census = cen
            for slot in range(4):
                vals = rd(mem, translate(SCRIPT_SLOTS + slot * SCRIPT_SIZE + VARS_OFF), f"<{NVARS}i")
                old = prev_vars.get(slot)
                if old is not None and old != vals:
                    diff = {i: (old[i], v) for i, v in enumerate(vals) if old[i] != v}
                    print(f"t{turn} vars slot {slot} {diff}", flush=True)
                elif old is None:
                    print(f"t{turn} vars slot {slot} init { {i: v for i, v in enumerate(vals) if v} }", flush=True)
                prev_vars[slot] = vals
            if turn % 64 == 0:
                banks = [rd(mem, translate(TRIBE_BASE + t * TRIBE_SIZE + BANK), "<I")[0] for t in range(4)]
                print(f"t{turn} bank {banks}", flush=True)
            if turn - first_turn >= max_turns:
                break


if __name__ == "__main__":
    main()

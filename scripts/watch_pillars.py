"""Live, read-only poll of the Reincarnation Centre's 8 standing-stone pillars during a level's
opening intro, to settle docs/cheat.md's open "do all 8 rise together, or one by one?" dispute
(static trace of 0x41c140/0x4a7d80/0x4a7eb0 says "all 8 in one uninterrupted tick"; the user's own
played-it memory says "staggered, just very close together").

Run from a fresh level load (restart the level, then start this script - or start this script
first, it retries find_game() until the process appears). Prints one line per turn once
0x89D17C bit 0x20 (Phase A, the RC pillar-spawn trigger) is first observed set, with each of the
8 pillar slots' own thing-id (tribe_struct+0xA0D), state (+0x2C), and height (+0x41, i16) resolved
through the generic id->pointer table (0x890390 + id*4, confirmed in dis.txt as
`mov reg, DWORD PTR [reg*4+0x890390]`). Ctrl+C once all 8 read state 6 and height has stopped
climbing.

Usage (inside the docker rig, see scripts/docker/capture.sh):
  scripts/docker/capture.sh scripts/watch_pillars.py [--every SECONDS]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
PHASE_FLAG = 0x89D17C
PLAYER_TRIBE = 0x89C6F0
TRIBE_BASE = 0x89D1C8
TRIBE_STRIDE = 0xC65
PILLAR_ARR_OFF = 0xA0D
THING_TABLE = 0x890390


def rd(mem, addr, fmt):
    mem.seek(addr)
    return struct.unpack(fmt, mem.read(struct.calcsize(fmt)))[0]


def main():
    every = 0.05
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--every":
            every = float(next(it))

    pid, translate = None, None
    while not pid:
        pid, translate = find_game()
        if not pid:
            time.sleep(0.2)
    print(f"attached to pid {pid}", flush=True)

    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        started = False
        last_line = None
        turns_since_full = 0
        while True:
            turn = rd(mem, translate(TURN), "<I")
            phase_byte = rd(mem, translate(PHASE_FLAG), "<B")
            bit = bool(phase_byte & 0x20)
            if bit and not started:
                started = True
                print(f"turn={turn} *** PHASE A FIRED (0x89D17C bit 0x20 set) ***", flush=True)
            if True:
                tribe_idx = rd(mem, translate(PLAYER_TRIBE), "<B")
                tribe = TRIBE_BASE + tribe_idx * TRIBE_STRIDE
                ids, states, heights = [], [], []
                for i in range(8):
                    wid = rd(mem, translate(tribe + PILLAR_ARR_OFF + i * 2), "<H")
                    ids.append(wid)
                    if wid == 0:
                        states.append(None)
                        heights.append(None)
                        continue
                    ptr = rd(mem, translate(THING_TABLE) + wid * 4, "<I")
                    if ptr == 0:
                        states.append(None)
                        heights.append(None)
                        continue
                    states.append(rd(mem, ptr + 0x2C, "<B"))
                    heights.append(rd(mem, ptr + 0x41, "<h"))
                line = f"turn={turn} ids={ids} states={states} heights={heights}"
                if line != last_line:
                    print(line, flush=True)
                    last_line = line
                if all(i != 0 for i in ids) and all(s == 6 for s in states if s is not None):
                    turns_since_full += 1
                    if turns_since_full > 40:
                        print("all 8 risen and settled, stopping", flush=True)
                        return
                else:
                    turns_since_full = 0
            time.sleep(every)


if __name__ == "__main__":
    main()

"""Live, read-only poll of the Reincarnation Centre's land-reservation flag (tribe+0x93D,
set/cleared by SET_REINCARNATION's native handler 0x48DC26 and by effect state 7's
"prepare rs land" completion, 0x50C840/docs/functions.tsv) alongside the 8 pillar slots
(tribe_struct+0xA0D), to see whether SET_REINCARNATION's own flag correlates with the
staggered pillar-appearance timing already observed (turns 37/40/41/44/45/48/49/52 on a
fresh level-1 load) - settling whether that opcode's path is actually what's running, or
something else entirely.

Usage (inside the docker rig, see scripts/docker/capture.sh):
  scripts/docker/capture.sh scripts/watch_rc_flags.py [--every SECONDS]
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
RC_FLAGS_OFF = 0x93D
RC_ANCHOR_X_OFF = 0x911
RC_ANCHOR_Z_OFF = 0x913
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
        last_line = None
        while True:
            turn = rd(mem, translate(TURN), "<I")
            phase_byte = rd(mem, translate(PHASE_FLAG), "<B")
            tribe_idx = rd(mem, translate(PLAYER_TRIBE), "<B")
            tribe = TRIBE_BASE + tribe_idx * TRIBE_STRIDE
            rc_flags = rd(mem, translate(tribe + RC_FLAGS_OFF), "<I")
            anchor_x = rd(mem, translate(tribe + RC_ANCHOR_X_OFF), "<H")
            anchor_z = rd(mem, translate(tribe + RC_ANCHOR_Z_OFF), "<H")
            ids = []
            for i in range(8):
                wid = rd(mem, translate(tribe + PILLAR_ARR_OFF + i * 2), "<H")
                ids.append(wid)
            line = (
                f"turn={turn} phase20={bool(phase_byte & 0x20)} "
                f"rc_flags=0x{rc_flags:x} bit0(prepared)={bool(rc_flags & 1)} "
                f"bit0x10000(reserved)={bool(rc_flags & 0x10000)} "
                f"anchor=({anchor_x},{anchor_z}) ids={ids}"
            )
            if line != last_line:
                print(line, flush=True)
                last_line = line
            time.sleep(every)


if __name__ == "__main__":
    main()

"""WRITES memory: kill every live person of TRIBE and person TYPE by setting its life (+0x6E) to 0; the exe's own
per-turn life step (0x4D43A0) then puts it in state 3 (death) like any other kill. Persons inside a building
(state 21) are skipped unless --housed. Usage: kill_units.py TRIBE TYPE [--max N] [--housed]"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
THING_TABLE = 0x890390


def main():
    tribe, typ = int(sys.argv[1]), int(sys.argv[2])
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10**6
    housed = "--housed" in sys.argv
    pid, translate = find_game()
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        mem.seek(translate(TURN))
        print("turn", struct.unpack("<I", mem.read(4))[0])
        mem.seek(translate(THING_TABLE))
        ptrs = struct.unpack("<4096I", mem.read(4096 * 4))
        done = 0
        for i, p in enumerate(ptrs):
            if not p or done >= limit:
                continue
            try:
                mem.seek(p + 0x2A)
                cls, t, st, _, _, tr = struct.unpack("<6B", mem.read(6))
            except OSError:
                continue
            if cls != 1 or t != typ or tr != tribe or st == 3 or (st == 21 and not housed):
                continue
            mem.seek(p + 0x6E)
            print(f"#{i} state {st} life {struct.unpack('<H', mem.read(2))[0]} -> 0")
            mem.seek(p + 0x6E)
            mem.write(struct.pack("<H", 0))
            done += 1


if __name__ == "__main__":
    main()

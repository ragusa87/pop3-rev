"""Force buildings' drawing for a screenshot: write draw class (+0x3A) and construction stage (+0x78) into the
given thing ids of the running game. Draw class 10 = the construction renderer (stage 0-3 picks the faces), 5 =
built (every face). WRITES game memory: rig only, never with a save you care about.

Usage (inside the docker rig):
  scripts/docker/capture.sh scripts/poke_building_stage.py DRAW_CLASS STAGE ID [ID...]
  e.g. ... poke_building_stage.py 10 2 625 626     then  ... 5 4 625 626 to restore a built hut
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

THING_TABLE = 0x890390


def main():
    draw_class, stage, ids = int(sys.argv[1]), int(sys.argv[2]), [int(a) for a in sys.argv[3:]]
    pid, translate = find_game()
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        mem.seek(translate(THING_TABLE))
        ptrs = struct.unpack("<4096I", mem.read(4096 * 4))
        for i in ids:
            mem.seek(ptrs[i] + 0x2A)
            cls, typ = mem.read(2)
            if cls != 2:
                print(f"#{i} is class {cls}, skipped")
                continue
            mem.seek(ptrs[i] + 0x3A)
            mem.write(bytes([draw_class]))
            mem.seek(ptrs[i] + 0x78)
            mem.write(bytes([stage]))
            print(f"#{i} building type {typ}: draw class {draw_class}, stage {stage}")


if __name__ == "__main__":
    main()

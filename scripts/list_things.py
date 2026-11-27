"""Read-only: list every live thing of the running game except trees/plants (class 5 types 1-8) and effects
(class 7), with class/type/state/tribe and position in world units and cells (512 units a cell).

Usage (inside the docker rig):  scripts/docker/capture.sh scripts/list_things.py [CLASS ...]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
THING_TABLE = 0x890390


def main():
    classes = {int(a) for a in sys.argv[1:]}
    pid, translate = find_game()
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(translate(TURN))
        print("turn", struct.unpack("<I", mem.read(4))[0])
        mem.seek(translate(THING_TABLE))
        ptrs = struct.unpack("<4096I", mem.read(4096 * 4))
        for i, p in enumerate(ptrs):
            if not p:
                continue
            try:
                mem.seek(p + 0x2A)
                cls, typ, st, st2, _, tribe = struct.unpack("<6B", mem.read(6))
                mem.seek(p + 0x3D)
                x, z, h = struct.unpack("<HHh", mem.read(6))
            except OSError:
                continue
            if classes and cls not in classes:
                continue
            if not classes and (cls in (0, 7) or (cls == 5 and typ <= 8)):
                continue
            print(f"#{i} class {cls} type {typ} state {st}/{st2} tribe {tribe} at ({x},{z}) h {h} cell ({x / 512:.1f},{z / 512:.1f})")


if __name__ == "__main__":
    main()

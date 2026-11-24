"""Make the campaign star map launch a given level: writes the level id into the currently
selected planet's record (`[0x5F13BC] + [0x5F13B0]*0x34 + 0x28`), the value the star map passes
to the campaign start routine 0x4858F0 on Return. Run while the star map is on screen, then
press Return (the label already shows the new level). See docs/cheat.md "Level 7 RC, live".

Usage (inside the docker rig): scripts/docker/capture.sh scripts/set_star_map_level.py 7
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

SELECTED = 0x5F13B0
PLANETS = 0x5F13BC
STRIDE = 0x34
LEVEL_FIELD = 0x28


def main():
    level = int(sys.argv[1])
    pid, translate = find_game()
    if not pid:
        sys.exit("game not running")
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        mem.seek(translate(SELECTED))
        idx = struct.unpack("<i", mem.read(4))[0]
        mem.seek(translate(PLANETS))
        base = struct.unpack("<I", mem.read(4))[0]
        addr = base + idx * STRIDE + LEVEL_FIELD
        mem.seek(addr)
        old = struct.unpack("<i", mem.read(4))[0]
        mem.seek(addr)
        mem.write(struct.pack("<i", level))
    print(f"planet {idx}: level {old} -> {level}")


if __name__ == "__main__":
    main()

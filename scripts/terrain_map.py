"""Read-only: ASCII land/sea map of a cell window of the running game (# land, ~ sea per the terrain-type sea flag),
with optional marks. Usage: terrain_map.py X0 X1 Z0 Z1 [x,z,char ...]   (cells, inclusive, wrapping at 128)"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

CELLS, TERRAIN = 0x8A03F0, 0x5AA328


def main():
    x0, x1, z0, z1 = (int(a) for a in sys.argv[1:5])
    marks = {}
    for m in sys.argv[5:]:
        x, z, c = m.split(",")
        marks[(int(x) % 128, int(z) % 128)] = c
    pid, translate = find_game()
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(translate(CELLS))
        cells = mem.read(128 * 128 * 16)
        mem.seek(translate(TERRAIN))
        terrain = mem.read(16 * 14)
    xs = [x % 128 for x in range(x0, x1 + 1)]
    print("      " + "".join(str(x // 10 % 10) for x in xs))
    print("      " + "".join(str(x % 10) for x in xs))
    for z in range(z0, z1 + 1):
        zz = z % 128
        row = ""
        for x in xs:
            if (x, zz) in marks:
                row += marks[(x, zz)]
                continue
            nib = cells[(zz * 128 + x) * 16] & 0xF
            row += "~" if terrain[nib * 14] & 2 else "#"
        print(f"{zz:4d}  {row}")


if __name__ == "__main__":
    main()

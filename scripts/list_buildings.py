"""Read-only: list every live building (class 2) and wood-stock companion (class 9) of the running game with
state, mesh (+0x63), draw class (+0x3A), stage (+0x78), companion ids (+0x82/+0x92/+0x94) and stock (+0x96).

Usage (inside the docker rig):  scripts/docker/capture.sh scripts/list_buildings.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
THING_TABLE = 0x890390
POOL, POOL_END = 0x8E0428, 0x8E0428 + 2000 * 0xB3


def main():
    pid, translate = find_game()
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(translate(TURN))
        print("turn", struct.unpack("<I", mem.read(4))[0])
        mem.seek(translate(THING_TABLE))
        ptrs = struct.unpack("<4096I", mem.read(4096 * 4))
        lo, hi = translate(POOL), translate(POOL_END)
        for i, p in enumerate(ptrs):
            if not lo <= p < hi:
                continue
            mem.seek(p)
            b = mem.read(0xB3)
            if b[0x2A] not in (2, 9) or b[0xC] & 1:
                continue
            x, z, h = struct.unpack_from("<HHh", b, 0x3D)
            words = {k: struct.unpack_from("<H", b, k)[0] for k in (0x63, 0x82, 0x92, 0x94)}
            print(f"#{i} class {b[0x2A]} type {b[0x2B]} state {b[0x2C]}/{b[0x2D]} tribe {b[0x2F]} pos {x},{z},{h} "
                  f"mesh {words[0x63]} draw class {b[0x3A]} stage {b[0x78]} companions {words[0x82]}/{words[0x92]}/"
                  f"{words[0x94]} stock {struct.unpack_from('<h', b, 0x96)[0]}")


if __name__ == "__main__":
    main()

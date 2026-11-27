"""WRITES memory: point the local player's camera at a cell (tribe record +0x24, the camera focus x/z, as
ww_to_sea.py does). Usage: cam_focus.py CELL_X CELL_Z   (fractional cells allowed, 512 world units a cell)"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TRIBES, TSTRIDE, PLAYER = 0x89D1C8, 0xC65, 0x89C6F0


def main():
    x, z = (int(float(a) * 512) % 65536 for a in sys.argv[1:3])
    pid, translate = find_game()
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        mem.seek(translate(PLAYER))
        t = TRIBES + mem.read(1)[0] * TSTRIDE
        mem.seek(translate(t + 0x24))
        print("was", struct.unpack("<HH", mem.read(4)))
        mem.seek(translate(t + 0x24))
        mem.write(struct.pack("<HH", x, z))
        print("now", (x, z))


if __name__ == "__main__":
    main()

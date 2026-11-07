"""Live, read-only poll of the mouse_device global object (0xD0595C, docs/functions.tsv row),
to nail down the still-open field layout TODO.md flagged as "not yet live-verified": +0x14,
+0x28/+0x2c, the +0x38 rect, and the +0x1c lazily-allocated 0xf8-byte sub-object.

Already statically confirmed (docs/functions.tsv 0xd0595c): +0x1c sub-object pointer
(mouse_input_context), +0x20/+0x24 absolute (x,y) dword pair (mouse_cursor_x/y).

Usage: move the mouse (e.g. `scripts/docker/xdo.sh mousemove X Y`) while this runs, to correlate
field changes against known cursor positions.

  scripts/docker/capture.sh scripts/watch_mouse.py [--every SECONDS]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

BASE = 0xD0595C
FIELDS = [
    (0x14, "<i", "f14"),
    (0x1C, "<I", "subobj_ptr"),
    (0x20, "<i", "x"),
    (0x24, "<i", "y"),
    (0x28, "<i", "f28"),
    (0x2C, "<i", "f2c"),
    (0x38, "<i", "rect_l"),
    (0x3C, "<i", "rect_t"),
    (0x40, "<i", "rect_r"),
    (0x44, "<i", "rect_b"),
]


def main():
    every = 0.1
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
        last = None
        while True:
            vals = []
            for off, fmt, label in FIELDS:
                mem.seek(translate(BASE) + off)
                v = struct.unpack(fmt, mem.read(struct.calcsize(fmt)))[0]
                vals.append(f"{label}={v}")
            line = " ".join(vals)
            if line != last:
                print(line, flush=True)
                last = line
            time.sleep(every)


if __name__ == "__main__":
    main()

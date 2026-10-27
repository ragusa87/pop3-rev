"""Live, read-only poll of the camera's position/zoom/rotation and the render-block
distance/bend/shift fields, to compare level 1's opening flyby (open-populous
docs/specs/ai-scripts.md "Worked example: level 1's opening flyby") against
pop3-rev-analysis.md's "Landscape projection" and game-client/src/flyby.rs's zoom<->distance
guess.

Waits for either D3DPOPTB.EXE or POPTB.EXE to appear (no root needed for that part), then polls
memory (root needed) and prints a line whenever any field changes, prefixed by a wall-clock
timestamp and the turn counter (12/s). Run this before or after launching the game - it waits
either way - then play into level 1 and let the opening flyby fire on its own (script-gated on
game turn > 70, ~6s after you get control); Ctrl+C once it's done.

Field layout (docs/cheat.md "Camera" / open-populous pop3-rev-analysis.md "Landscape
projection"):
- cam_x/cam_z: 0x89ce49/0x89ce45 (dword, world units - same scale as unit positions). Confirmed
  this session via process_cmd's arrow-key pan handlers (switchD_004aabca caseD_3a/36: +-200 per
  press, clamped to +-0x6e00) and the terrain-strip generator, which reads both every frame.
- zoom_tgt/zoom_cur: 0x89ce3f/0x89ce40 (byte, 0-50) - the UI zoom slider's target/current step
  (caseD_32-35; current chases target by <=3/tick, a smoothing pair, not itself the render
  distance).
- K/D/S: 0x87ca5c/0x87ca64/0x87ca68 (dword) - bend/distance/perspective-shift, already measured
  live in pop3-rev-analysis.md "Landscape projection" (D in render units, /256 = cells, default
  6500 = 25.4 cells behind the focus).
- m0-m8: 0x74a354..0x74a374 (9x dword, 14-bit fixed point) - the camera rotation matrix, copied
  fresh into the draw state every frame from a live pointer at 0x74a350 (clear_land_draw_state,
  0x46E700/0x46e168). Yaw is not yet decoded out of this matrix - logged raw here for post-hoc
  correlation against the flyby script's own ANGLE keyframes (0-2047, same convention as
  nature::angle_yaw).
- turn: 0x89d188 (dword) - global turn counter, 12/s.

`0x74a350` (the matrix's per-frame source pointer) was traced statically this session: it
resolves to `0x89D1C8 + tribe*0xC65` (the already-documented tribe_struct base/stride, docs/cheat.md
"Relevant addresses") for the LOCAL PLAYER's own tribe (index byte at `0x89C6F0`, same
`PLAYER_TRIBE_ADDR`), offset +0x0 - i.e. the matrix is tribe_struct's own first 36 bytes, not a
separate camera struct. So any position/distance field sitting alongside it, if one exists, is
somewhere in tribe_struct's still-undocumented range +0x24..+0x880 (known fields resume at +0x881,
person_units). `--scan-tribe` dumps that whole range as dwords and reports only the ones that
change between polls (each line tagged with the game turn counter, not just wall-clock, so changes
can be correlated against ai-scripts.md's turn-based keyframe timing), to narrow candidates live
instead of guessing offsets by hand - cross-check hits against pop3-rev's docs/cheat.md tribe_struct
field list (mana/unit-list fields already explained there are noise for this purpose, not camera
candidates).

sudo python3 watch_camera.py [--every SECONDS]
sudo python3 watch_camera.py --scan-tribe [--every SECONDS]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

FIELDS = [
    (0x89CE49, "<i", "cam_x"),
    (0x89CE45, "<i", "cam_z"),
    (0x89CE3F, "<B", "zoom_tgt"),
    (0x89CE40, "<B", "zoom_cur"),
    (0x87CA5C, "<i", "K"),
    (0x87CA64, "<i", "D"),
    (0x87CA68, "<i", "S"),
    (0x74A354, "<i", "m0"),
    (0x74A358, "<i", "m1"),
    (0x74A35C, "<i", "m2"),
    (0x74A360, "<i", "m3"),
    (0x74A364, "<i", "m4"),
    (0x74A368, "<i", "m5"),
    (0x74A36C, "<i", "m6"),
    (0x74A370, "<i", "m7"),
    (0x74A374, "<i", "m8"),
    (0x89D188, "<I", "turn"),
]


TRIBE_BASE = 0x89D1C8
TRIBE_STRIDE = 0xC65
PLAYER_TRIBE_ADDR = 0x89C6F0
SCAN_LO, SCAN_HI = 0x00, 0x880  # undocumented tribe_struct range (known fields resume at +0x881)


def scan_tribe(mem, translate, every):
    turn_addr = translate(0x89D188)
    last = None
    n_words = (SCAN_HI - SCAN_LO) // 4
    while True:
        mem.seek(translate(PLAYER_TRIBE_ADDR))
        tribe = mem.read(1)[0]
        base = TRIBE_BASE + tribe * TRIBE_STRIDE + SCAN_LO
        mem.seek(translate(base))
        words = struct.unpack(f"<{n_words}I", mem.read(n_words * 4))
        mem.seek(turn_addr)
        turn = struct.unpack("<I", mem.read(4))[0]
        if last is not None:
            changes = [
                f"+0x{SCAN_LO + i * 4:03x}: {last[i]:#x}->{w:#x}"
                for i, w in enumerate(words)
                if w != last[i]
            ]
            if changes:
                print(f"{time.time():.2f}  turn={turn}  tribe={tribe}  " + "  ".join(changes), flush=True)
        last = words
        time.sleep(every)


def main():
    every = 0.08
    scan = False
    args = iter(sys.argv[1:])
    for a in args:
        if a == "--every":
            every = float(next(args))
        elif a == "--scan-tribe":
            scan = True

    pid, translate = find_game()
    while pid is None:
        print("# waiting for D3DPOPTB.EXE/POPTB.EXE...", file=sys.stderr, flush=True)
        time.sleep(2.0)
        pid, translate = find_game()
    print(f"# found pid {pid}, watching...", file=sys.stderr, flush=True)

    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        if scan:
            scan_tribe(mem, translate, every)
            return
        resolved = [(translate(addr), fmt, label) for addr, fmt, label in FIELDS]
        last = None
        while True:
            values = []
            for addr, fmt, label in resolved:
                mem.seek(addr)
                values.append(f"{label}={struct.unpack(fmt, mem.read(struct.calcsize(fmt)))[0]}")
            line = "  ".join(values)
            if line != last:
                print(f"{time.time():.2f}  {line}", flush=True)
                last = line
            time.sleep(every)


if __name__ == "__main__":
    main()

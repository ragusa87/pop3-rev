"""Measure a simple Blast: per-turn position of the blast effect itself (class 7, state 1,
"kind=blast" rows, now also its own radius/push-constant/vertical-constant fields) plus
position/velocity/life of every living person ("kind=person" rows, any tribe, blown or not) -
join them on `turn` to get the real distance `d` and check it against the formula in "Blast
push and flight" (f = (R - d) / R).

v3: disassembly of the per-turn push code (0x50b9a6-0x50ba05, called from the shared simple-
blast turn handler) showed R, the "140" push constant and the "98" vertical constant are NOT
immediates in that code - they're read live from the blast instance's own fields every turn:
`R` = DWORD at +0x6c (same field the doc already names "radius"), the horizontal push
constant = WORD at +0x74, the vertical push constant = WORD at +0x78 (both read via `movsx`,
so i16). This means the "140"/"98" figures aren't universal constants to verify once - they're
per-instance config that whatever spell creates the blast (Blast, Firestorm's fireball,
Volcano's fireball) sets at init, and R itself can legitimately differ turn to turn within one
blast's own 3-turn life. Logging them straight from the blast's own struct is strictly better
than inferring them from a pushed person's velocity delta (which is what v2 analysis had to do,
and which could only get the ratio of the true constant to an ASSUMED R=1280).

sudo python3 measure_blast.py > blast_log.csv

Setup for a clean trial:
- one lone, allied brave standing alone on flat ground, far from buildings/other units
- start the logger BEFORE casting (it logs every person every turn, not just blown ones,
  so the pre-push distance and any direct damage tick are both captured this time)
- cast Blast so the brave sits at a known distance from the impact cell
- let it run until the unit lands and stops sliding
- repeat at several distances (0, 1, 1.5, 2, 2.5+ cells) and on sloped ground

v1 of this script only logged a person once its "blown" flag was already set, which turned
out to be too late to check the push formula itself: the first visible sample was always
already past the push (and often past more than one of the blast's 3 ticks, with the person
already moved away from its true at-cast distance) and could never see a pre-push health
value to catch direct (non-push) damage. It was, however, enough to pin down Person physics
exactly: gravity -32/turn and air drag -2/turn on vel while airborne, friction 28/turn on
landing - all confirmed live AND cross-checked against the movement-profile table itself
(0x5A7B90 row 2 = brave, read straight from the EXE on disk, no running game needed):
(256, 170, 64, 110, 192, 512, 192, 512, 384, 32, 28, 72, 1) - +0x12 (word 9) = 32, +0x14
(word 10) = 28, +0x8/+0xC (words 4/6) = 192, matching "Person physics" exactly. The one
apparent mismatch (live trials twice saturated at exactly vel_x = vel_z = -190, not -192) is
resolved, not a correction: a push that hits the 192 cap and that same turn's -2 air drag
both happen before the turn ends, so the first sample we can ever read back is already
192 - 2 = 190 - the pipeline just never exposes the untouched, uncapped value.

Based on docs/cheat.md's find_game() + the "Unit record" field offsets in
pop3-rev-analysis.md ("Person statuses" / "Movement"). `pos` layout (x: i16 low word of the
dword at +0x3D, z: i16 high word at +0x3F, height: i16 at +0x41) confirmed from the
disassembly of the person physics step at 0x4e6d1d/0x4e6d6d (person physics, "blown" push
application).
"""
import os
import struct
import sys
import time

UNIT_ARRAY = 0x8E0428
UNIT_SIZE = 0xB3
UNIT_COUNT = 2000
TURN_COUNTER = 0x89D188

OFF_CLASS = 0x2A
OFF_TRIBE = 0x2F
OFF_FLAGS = 0xC       # u32; bit 0x2000 airborne, bit 0x80000 blown (set by a blast push)
OFF_POS_X = 0x3D      # i16, low word of the dword at +0x3D
OFF_POS_Z = 0x3F      # i16, high word of that same dword
OFF_POS_H = 0x41      # i16, height/altitude - confirmed via 0x4e6d1d/0x4e6d6d (vel added into these words)
OFF_VEL_X = 0x49      # i16
OFF_VEL_Y = 0x4B      # i16, vertical
OFF_VEL_Z = 0x4D      # i16
OFF_MAX_LIFE = 0x6C   # u16
OFF_LIFE = 0x6E       # u16

OFF_STATE = 0x2C      # u8; for class 7 (effect), state 1 = simple blast (pop3-rev-analysis.md "Effect state")
OFF_RADIUS = 0x6C     # i32, R in "Blast push and flight" - read live each turn, not a fixed 1280
OFF_PUSH_K = 0x74     # i16, horizontal push constant ("140"), per-instance, set at init
OFF_VERT_K = 0x78     # i16, vertical push constant ("98"), per-instance, set at init

BLOWN_BIT = 0x80000
CLASS_PERSON = 1
CLASS_EFFECT = 7
STATE_SIMPLE_BLAST = 1


def find_game():
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().lower()
        except OSError:
            continue
        if not cmd.startswith(b"c:\\"):
            continue
        if b"d3dpoptb.exe" in cmd:
            return int(pid), (lambda addr: addr)
        if b"poptb.exe" in cmd:
            sys.path.insert(0, "/home/laurent/compile/pop3-rev/.claude/skills/original-game-spec/scripts")
            from addrmap import AddrMap
            return int(pid), AddrMap.load().to_poptb
    return None, None


def main():
    pid, translate = find_game()
    if pid is None:
        print("game not running", file=sys.stderr)
        return

    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        def read(addr, size):
            mem.seek(translate(addr))
            return mem.read(size)

        print("turn,kind,unit_idx,flags,x,z,height,vel_x,vel_y,vel_z,life,max_life,radius,push_k,vert_k")
        last_turn = None
        while True:
            turn = struct.unpack("<I", read(TURN_COUNTER, 4))[0]
            if turn == last_turn:
                time.sleep(0.01)
                continue
            last_turn = turn

            for idx in range(UNIT_COUNT):
                base = UNIT_ARRAY + idx * UNIT_SIZE
                cls = read(base + OFF_CLASS, 1)[0]

                if cls == CLASS_EFFECT:
                    state = read(base + OFF_STATE, 1)[0]
                    if state != STATE_SIMPLE_BLAST:
                        continue
                    x = struct.unpack("<h", read(base + OFF_POS_X, 2))[0]
                    z = struct.unpack("<h", read(base + OFF_POS_Z, 2))[0]
                    h = struct.unpack("<h", read(base + OFF_POS_H, 2))[0]
                    radius = struct.unpack("<i", read(base + OFF_RADIUS, 4))[0]
                    push_k = struct.unpack("<h", read(base + OFF_PUSH_K, 2))[0]
                    vert_k = struct.unpack("<h", read(base + OFF_VERT_K, 2))[0]
                    print(f"{turn},blast,{idx},,{x},{z},{h},,,,,,{radius},{push_k},{vert_k}")
                    continue

                if cls != CLASS_PERSON:
                    continue
                flags = struct.unpack("<I", read(base + OFF_FLAGS, 4))[0]

                x = struct.unpack("<h", read(base + OFF_POS_X, 2))[0]
                z = struct.unpack("<h", read(base + OFF_POS_Z, 2))[0]
                h = struct.unpack("<h", read(base + OFF_POS_H, 2))[0]
                vx, vy, vz = struct.unpack("<hhh", read(base + OFF_VEL_X, 6))
                max_life, life = struct.unpack("<HH", read(base + OFF_MAX_LIFE, 4))

                print(f"{turn},person,{idx},0x{flags:x},{x},{z},{h},{vx},{vy},{vz},{life},{max_life},,,")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

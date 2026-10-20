"""Measure a simple Blast: per-turn position of the blast effect itself (class 7, state 1,
"kind=blast" rows) plus position/velocity/life of every unit it is pushing ("kind=person"
rows) - join them on `turn` to get the real distance `d` and check it against the formula
in "Blast push and flight" (f = (R - d) / R, R = 1280).

sudo python3 measure_blast.py > blast_log.csv

Setup for a clean trial:
- one lone, allied brave standing alone on flat ground, far from buildings/other units
- cast Blast so the brave sits at a known distance from the impact cell
- let it run until the unit lands and stops sliding (logging stops on its own)
- repeat at several distances (0, 1, 1.5, 2, 2.5+ cells) and on sloped ground

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

        print("turn,kind,unit_idx,flags,x,z,height,vel_x,vel_y,vel_z,life,max_life")
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
                    print(f"{turn},blast,{idx},,{x},{z},{h},,,,,")
                    continue

                if cls != CLASS_PERSON:
                    continue
                flags = struct.unpack("<I", read(base + OFF_FLAGS, 4))[0]
                if not (flags & BLOWN_BIT):
                    continue

                x = struct.unpack("<h", read(base + OFF_POS_X, 2))[0]
                z = struct.unpack("<h", read(base + OFF_POS_Z, 2))[0]
                h = struct.unpack("<h", read(base + OFF_POS_H, 2))[0]
                vx, vy, vz = struct.unpack("<hhh", read(base + OFF_VEL_X, 6))
                max_life, life = struct.unpack("<HH", read(base + OFF_MAX_LIFE, 4))

                print(f"{turn},person,{idx},0x{flags:x},{x},{z},{h},{vx},{vy},{vz},{life},{max_life}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

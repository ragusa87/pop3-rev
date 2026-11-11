"""Live check: what model id / draw class does a REAL ground-fire scenery object (class 5, type
0xA, "fire" per docs/unit_types) actually carry in its own `+0x33`/`+0x3A` fields once the exe has
spawned and initialised one - settling the open question in docs/trace-backlog.md ("Ground fire /
flame visual scale"), where a static trace of `0x4A66C0`'s own per-type dispatch landed on model id
5, an apparently-EMPTY `OBJS0-0.DAT` slot (can't be right for a fire that's clearly visible in play).

Cast Lightning or Firestorm at bare ground (no building/tree) while this is running - every NEW
class-5/type-0xA object that appears gets its own fields printed once, then re-printed any turn one
of the watched fields changes (so you can see +0x68/+0x82's own intensity ramp live too, per
pop3-rev-analysis.md "Ground fire, ignited trees...").

sudo python3 scan_ground_fire.py   (or scripts/docker/capture.sh scripts/scan_ground_fire.py in the
Docker rig - see docs/cheat.md "Docker headless rig")

Based on docs/cheat.md's find_game() + the `unit_array` field offsets already confirmed live in
measure_blast.py (unit_array 0x8E0428, 0xB3 bytes/record, 2000 slots; OFF_CLASS 0x2A).
"""
import os
import struct
import sys
import time

UNIT_ARRAY = 0x8E0428
UNIT_SIZE = 0xB3
UNIT_COUNT = 2000
TURN_COUNTER = 0x89D188

OFF_CLASS = 0x2A   # u8
OFF_TYPE = 0x2B    # u8
OFF_STATE = 0x2C   # u8
OFF_TRIBE = 0x2F   # u8
OFF_POS_X = 0x3D   # i16, low word of the dword at +0x3D
OFF_POS_Z = 0x3F   # i16, high word of that same dword
OFF_POS_H = 0x41   # i16
OFF_MODEL_ID = 0x33   # u16 - the "index" arg 0x4EE700 stores (own functions.tsv row)
OFF_DRAW_CLASS = 0x3A  # u8 - row index into table 0x5A6AF8
OFF_BURN_LEN = 0x7C    # i16 - the burn-length countdown (0x4A7170's own row)
OFF_INTENSITY_BASE = 0x7E  # i16 - baseline flame-intensity
OFF_INTENSITY_CUR = 0x68   # i16 - current flame-intensity accumulator
OFF_INTENSITY_RATE = 0x82  # i16 - per-tick decay rate

CLASS_SCENERY = 5
TYPE_FIRE = 0xA


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

        print("turn,idx,model_id,draw_class,burn_len,intensity_cur,intensity_base,intensity_rate,x,z,height,tribe,state", flush=True)
        last_turn = None
        last_seen = {}
        while True:
            turn = struct.unpack("<I", read(TURN_COUNTER, 4))[0]
            if turn == last_turn:
                time.sleep(0.02)
                continue
            last_turn = turn

            for idx in range(UNIT_COUNT):
                base = UNIT_ARRAY + idx * UNIT_SIZE
                cls = read(base + OFF_CLASS, 1)[0]
                if cls != CLASS_SCENERY:
                    continue
                typ = read(base + OFF_TYPE, 1)[0]
                if typ != TYPE_FIRE:
                    continue

                state = read(base + OFF_STATE, 1)[0]
                tribe = read(base + OFF_TRIBE, 1)[0]
                model_id = struct.unpack("<H", read(base + OFF_MODEL_ID, 2))[0]
                draw_class = read(base + OFF_DRAW_CLASS, 1)[0]
                burn_len = struct.unpack("<h", read(base + OFF_BURN_LEN, 2))[0]
                inten_cur = struct.unpack("<h", read(base + OFF_INTENSITY_CUR, 2))[0]
                inten_base = struct.unpack("<h", read(base + OFF_INTENSITY_BASE, 2))[0]
                inten_rate = struct.unpack("<h", read(base + OFF_INTENSITY_RATE, 2))[0]
                x = struct.unpack("<h", read(base + OFF_POS_X, 2))[0]
                z = struct.unpack("<h", read(base + OFF_POS_Z, 2))[0]
                h = struct.unpack("<h", read(base + OFF_POS_H, 2))[0]

                key = (idx, model_id, draw_class, burn_len, inten_cur)
                if last_seen.get(idx) == key:
                    continue
                last_seen[idx] = key
                print(f"{turn},{idx},{model_id},{draw_class},{burn_len},{inten_cur},{inten_base},{inten_rate},{x},{z},{h},{tribe},{state}", flush=True)


if __name__ == "__main__":
    main()

"""Per turn: pre-fights and fights, and with --fire firewarriors, their shots 8/6 and the life people lose.

usage: fightwatch.py [--fire] [--no-fights]
"""
import struct
import sys
import time

sys.path.insert(0, "/home/laurent/compile/pop3-rev/.claude/skills/original-game-spec/scripts")
from livemem import find_game

TURN = 0x89D188
FIGHTS, PRE_FIGHTS = 0x890358, 0x89035C
UNIT_PTRS = 0x890390
UNIT_POOL, UNIT_SIZE, UNIT_COUNT = 0x8E0428, 0xB3, 2000

FW_STATES = {0x28: "aim", 0x2C: "throw", 0x2D: "reload"}


def rd(mem, addr, fmt):
    mem.seek(addr)
    size = struct.calcsize(fmt)
    data = mem.read(size)
    if len(data) < size:
        raise OSError("short read")
    return struct.unpack(fmt, data)


def person(mem, uid):
    if not uid:
        return None
    (p,) = rd(mem, UNIT_PTRS + 4 * uid, "<I")
    cls, typ, st, sub, _, tribe = rd(mem, p + 0x2A, "<6B")
    (hp,) = rd(mem, p + 0x6E, "<h")
    (timer,) = rd(mem, p + 0x70, "<h")
    x, z = rd(mem, p + 0x3D, "<2H")
    return f"#{uid} t{typ} tr{tribe} st{st}/{sub} hp{hp} tm{timer} ({x},{z})"


def walk(mem, head, kind):
    (p,) = rd(mem, head, "<I")
    out = []
    while p:
        (cid,) = rd(mem, p + 0x24, "<H")
        if kind == "fight":
            (n,) = rd(mem, p + 0x68, "<b")
            ids = rd(mem, p + 0x70, "<6H")
            (ang,) = rd(mem, p + 0x26, "<H")
            out.append(f"FIGHT #{cid} n{n} ang{ang}: " + " | ".join(filter(None, (person(mem, i) for i in ids))))
        else:
            a, b = rd(mem, p + 0x6A, "<2H")
            out.append(f"PRE #{cid}: A {person(mem, a)} | B {person(mem, b)}")
        (p,) = rd(mem, p + 0x8, "<I")
    return out


def units(mem):
    """Every live unit of the pool: {id: record bytes}."""
    mem.seek(UNIT_POOL)
    pool = mem.read(UNIT_SIZE * UNIT_COUNT)
    if len(pool) < UNIT_SIZE * UNIT_COUNT:
        raise OSError("short read")
    out = {}
    for i in range(UNIT_COUNT):
        r = pool[i * UNIT_SIZE:(i + 1) * UNIT_SIZE]
        (flags,) = struct.unpack_from("<I", r, 0xC)
        if r[0x2A] and not flags & 1:
            out[struct.unpack_from("<H", r, 0x24)[0]] = r
    return out


def wrap(d):
    return (d + 0x8000) % 0x10000 - 0x8000


def pos(r):
    return struct.unpack_from("<2Hh", r, 0x3D)


def fire_lines(now, before):
    """Firewarriors at work, shots 8/6 in flight or gone, and people who lost life since the last turn."""
    out = []
    for uid, r in sorted(now.items()):
        if r[0x2A] == 1 and r[0x2B] == 6:
            a8, reload = r[0xA8], r[0xB2]
            if a8 not in FW_STATES and not reload:
                continue
            (target,) = struct.unpack_from("<H", r, 0x89)
            x, z, h = pos(r)
            line = (f"FW #{uid} tr{r[0x2F]} st{r[0x2C]}/{r[0x2D]} {FW_STATES.get(a8, hex(a8))} reload{reload}"
                    f" hp{struct.unpack_from('<h', r, 0x6E)[0]} ({x},{z},{h})")
            t = now.get(target)
            if target and t is not None:
                tx, tz, _ = pos(t)
                line += f" -> #{target} t{t[0x2B]} st{t[0x2C]}/{t[0x2D]} d({wrap(tx - x)},{wrap(tz - z)})"
            out.append(line)
        elif r[0x2A] == 8 and r[0x2B] == 6:
            shooter, target = struct.unpack_from("<2H", r, 0x88)
            aim = struct.unpack_from("<3h", r, 0x76)
            (speed,) = struct.unpack_from("<h", r, 0x5F)
            new = "" if uid in before else " NEW"
            out.append(f"SHOT #{uid}{new} from #{shooter} to #{target} mode{r[0x7C]} {pos(r)} aim{aim} spd{speed}")
    for uid, r in sorted(before.items()):
        if r[0x2A] == 8 and r[0x2B] == 6 and uid not in now:
            out.append(f"SHOT #{uid} GONE mode{r[0x7C]} at {pos(r)}")
    for uid, r in sorted(now.items()):
        old = before.get(uid)
        if r[0x2A] != 1 or old is None or old[0x2A] != 1:
            continue
        (hp,) = struct.unpack_from("<h", r, 0x6E)
        (was,) = struct.unpack_from("<h", old, 0x6E)
        if hp < was:
            x, z, h = pos(r)
            (vy,) = struct.unpack_from("<h", r, 0x4B)
            out.append(f"HURT #{uid} t{r[0x2B]} tr{r[0x2F]} {was}->{hp} (-{was - hp}) st{r[0x2C]} ({x},{z},{h}) vy{vy}")
    return out


def main():
    global TURN, FIGHTS, PRE_FIGHTS, UNIT_PTRS, UNIT_POOL
    fire, fights = "--fire" in sys.argv, "--no-fights" not in sys.argv
    pid, translate = find_game()
    if not pid:
        sys.exit("neither D3DPOPTB.EXE nor POPTB.EXE is running")
    TURN, FIGHTS, PRE_FIGHTS, UNIT_PTRS, UNIT_POOL = map(translate, (TURN, FIGHTS, PRE_FIGHTS, UNIT_PTRS, UNIT_POOL))
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        try:
            watch(mem, fire, fights)
        except OSError:
            sys.exit("the game closed")


def watch(mem, fire, fights):
    last_turn, before = None, {}
    while True:
        (turn,) = rd(mem, TURN, "<I")
        if turn != last_turn:
            last_turn = turn
            lines = walk(mem, PRE_FIGHTS, "pre") + walk(mem, FIGHTS, "fight") if fights else []
            if fire:
                now = units(mem)
                lines += fire_lines(now, before)
                before = now
            if lines:
                print(f"turn {turn}", *lines, sep="\n  ", flush=True)
        time.sleep(0.01)

if __name__ == "__main__":
    main()

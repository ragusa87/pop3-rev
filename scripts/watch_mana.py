"""Live, read-only poll of the player's own tribe mana fields, to correlate against the
spell-tab mana bar's visible state (full / draining / blinking) since the bar's own draw
code/fill-formula was not found by static disassembly (see docs/cheat.md and
docs/functions.tsv's 0x41A590/0x41AB63/0x49DAF0 rows for the search so far).

Prints a line only when any watched value changes, timestamped by the turn counter (12/s) so
samples line up with what you see on screen. Run this, then open the spell tab in-game and
watch the bar while doing things known to matter: sit idle with nothing learned, learn/charge
a spell, let it fill, let it idle again. Compare the printed bank/incoming/needed/reservoir
values (and each learned spell's charge/max) against what the bar visibly does at that moment.

Field layout from docs/cheat.md ("Relevant addresses") / pop3-rev-analysis.md ("Mana rules"):
tribe base = 0x89D1C8 + tribe_index*0xC65; bank +0x94D (u32, clamped 0..MAX_MANA); reservoir
+0x951; incoming +0x955 (not yet distributed); needed +0x959 (sum of charge[spell] over
available spells); charge[spell] +0x969+4*spell (spells 1-21, mana still needed for next
charge). struct_56B at 0x96070A+tribe*0x38 holds the discrete 0-15 charge *count* per spell
at +0x14+spell (low nibble) - a different quantity from charge[spell] above (that's "mana
remaining to fill the next charge", this is "how many charges already banked").

sudo python3 watch_mana.py
"""
import os
import struct
import sys
import time

TRIBE_BASE = 0x89D1C8
TRIBE_STRIDE = 0xC65
PLAYER_TRIBE_ADDR = 0x89C6F0
MAX_MANA_ADDR = 0x5AA408  # found this session inside tribe_distribute_mana (0x41AD1C)

OFF_BANK = 0x94D       # u32
OFF_RESERVOIR = 0x951  # u32
OFF_INCOMING = 0x955   # u32
OFF_NEEDED = 0x959     # u32
OFF_CHARGE = 0x969     # u32, +4*spell

STRUCT_56B_BASE = 0x96070A
STRUCT_56B_STRIDE = 0x38
OFF_LEARNED_MASK = 0x00  # u32 bitmask, bit (spell-1)
OFF_BLOCKED_MASK = 0x10  # u32 bitmask, bit (spell-1)
OFF_CHARGE_BYTE = 0x14   # +spell: low nibble = charge count (0-15), high nibble = gifted

NUM_SPELLS = 21


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

        def read_u32(addr):
            return struct.unpack("<I", read(addr, 4))[0]

        max_mana = read_u32(MAX_MANA_ADDR)
        print(f"# MAX_MANA = {max_mana}")

        last = None
        while True:
            tribe = read(PLAYER_TRIBE_ADDR, 1)[0]
            base = TRIBE_BASE + tribe * TRIBE_STRIDE
            bank = read_u32(base + OFF_BANK)
            reservoir = read_u32(base + OFF_RESERVOIR)
            incoming = read_u32(base + OFF_INCOMING)
            needed = read_u32(base + OFF_NEEDED)

            s56b = STRUCT_56B_BASE + tribe * STRUCT_56B_STRIDE
            learned = read_u32(s56b + OFF_LEARNED_MASK)
            blocked = read_u32(s56b + OFF_BLOCKED_MASK)
            charges = []
            for spell in range(1, NUM_SPELLS + 1):
                if not (learned & (1 << (spell - 1))):
                    continue
                byte = read(s56b + OFF_CHARGE_BYTE + spell, 1)[0]
                count, gifted = byte & 0xF, byte >> 4
                paused = bool(blocked & (1 << (spell - 1)))
                need = read_u32(base + OFF_CHARGE + spell * 4)
                charges.append((spell, count, gifted, paused, need))

            snapshot = (bank, reservoir, incoming, needed, tuple(charges))
            if snapshot != last:
                last = snapshot
                frac = bank / max_mana if max_mana else 0.0
                parts = ", ".join(
                    f"spell{sp}{'(paused)' if p else ''}: charges={c} gifted={g} need={n}"
                    for sp, c, g, p, n in charges
                )
                print(
                    f"tribe={tribe} bank={bank} ({frac:.4f} of MAX_MANA) reservoir={reservoir} "
                    f"incoming={incoming} needed={needed} | {parts}"
                )
                sys.stdout.flush()

            time.sleep(0.08)


if __name__ == "__main__":
    main()

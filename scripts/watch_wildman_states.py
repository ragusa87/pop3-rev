"""Live, read-only log of every wildman's person state (+0x2C) changes, turn by turn, plus any person
of any type entering state 15 (the only caller of the eat sounds 0x03/0xBE). Prints a per-state
wildman turn count at the end.

Usage (inside the docker rig):
  scripts/docker/capture.sh scripts/watch_wildman_states.py [--turns N] [--quiet]
"""
import collections
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills", "original-game-spec", "scripts"))
from livemem import find_game  # noqa: E402

TURN = 0x89D188
THING_TABLE = 0x890390
THING_COUNT = 0x1000
EAT_STATE = 15


def scan(mem, translate, table_ptrs):
    out = {}
    for idx, ptr in enumerate(table_ptrs):
        if not ptr:
            continue
        try:
            mem.seek(ptr + 0x2A)
            cls, typ, st, st2 = struct.unpack("<4B", mem.read(4))
            if cls != 1:
                continue
            mem.seek(ptr + 0x72)
            ref = struct.unpack("<H", mem.read(2))[0]
        except OSError:
            continue
        out[idx] = (typ, st, st2, ref)
    return out


def ref_desc(mem, translate, ref):
    if not ref:
        return "-"
    mem.seek(translate(THING_TABLE + ref * 4))
    ptr = struct.unpack("<I", mem.read(4))[0]
    if not ptr:
        return f"#{ref}(gone)"
    try:
        mem.seek(ptr + 0x2A)
        cls, typ = struct.unpack("<2B", mem.read(2))
    except OSError:
        return f"#{ref}(bad)"
    return f"#{ref}(class {cls} type {typ})"


def main():
    max_turns, quiet = 3000, False
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--turns":
            max_turns = int(next(it))
        elif a == "--quiet":
            quiet = True

    pid = None
    while not pid:
        pid, translate = find_game()
        if not pid:
            time.sleep(0.2)
    print(f"attached to pid {pid}", flush=True)

    hist = collections.Counter()
    eat_hits = []
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        last_turn, first_turn, prev = None, None, {}
        while True:
            mem.seek(translate(TURN))
            turn = struct.unpack("<I", mem.read(4))[0]
            if turn == last_turn:
                time.sleep(0.01)
                continue
            last_turn = turn
            first_turn = first_turn if first_turn is not None else turn
            mem.seek(translate(THING_TABLE))
            ptrs = struct.unpack(f"<{THING_COUNT}I", mem.read(THING_COUNT * 4))
            now = scan(mem, translate, ptrs)
            for idx, (typ, st, st2, ref) in now.items():
                if typ == 1:
                    hist[st] += 1
                if st == EAT_STATE:
                    eat_hits.append((turn, idx, typ))
                old = prev.get(idx)
                if (typ == 1 or st == EAT_STATE) and (old is None or old[1] != st) and not quiet:
                    print(f"t{turn} #{idx} type {typ}: state {old[1] if old else '?'} -> {st} sub {st2} ref {ref_desc(mem, translate, ref)}", flush=True)
            prev = now
            if turn - first_turn >= max_turns:
                break
    print(f"wildman state-turns over {max_turns} turns: {dict(sorted(hist.items()))}")
    print(f"persons seen in state {EAT_STATE}: {len(eat_hits)} {eat_hits[:20]}")


if __name__ == "__main__":
    main()

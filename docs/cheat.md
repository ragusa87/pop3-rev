# Cheating the original game, for testing

Not implementation work: this is a toolbox for playing the real `D3DPOPTB.EXE`/`POPTB.EXE` with
spells unlocked and charged, to visually check a traced mechanic (e.g. Firestorm, Erosion) against
the real game instead of only reading disassembly. Two kinds of edits:

- **File edits** (level `.hdr`, `SAVE/CONFIG00.DAT`): persist to disk, need the game restarted to
  take effect, low risk if backed up first.
- **Live memory edits**: instant, need the game already running and `sudo` (ptrace), never
  persisted - gone the moment the game restarts unless re-applied, and some fields get overwritten
  by the game's own logic shortly after (see "Open problems").

Always back up before writing a file: `cp -n original backup_claude/original` (the `-n` makes it a
no-op, not an overwrite, if already backed up).

## Level file: unlock every spell

`levels/levlNNNN.hdr` (616 bytes), offset 0, `u32` `SpellsAvailable`, bit N = spell model N
(level-format.md). Setting it to `0xFFFFFFFF` marks every spell "known" from the start:

```python
import struct
p = ".../levels/levl2001.hdr"   # level 1
b = bytearray(open(p, "rb").read())
struct.pack_into("<I", b, 0, 0xFFFFFFFF)
open(p, "wb").write(b)
```

- This mask is level-global, not per-tribe: the AI opponent(s) get every spell too.
- Bits 18 (armageddon), 20 (bloodlust), 21 (teleport) are the exe's "hidden" spells, normally never
  offered (pop3-rev-analysis.md "Charges and mana"); forcing them on did **not** cause the one crash
  seen this session (that turned out to be an unrelated `ddraw` DLL override, see below) but keep it
  in mind if something misbehaves specifically with one of those three.
- "Known" still needs mana to actually charge a spell; this alone doesn't grant instant charges
  (see "Live memory: fill every charge").

## Save file: force a resolution index

`SAVE/CONFIG00.DAT` (177 bytes), offset 0, one `BYTE`, `RESOLUTION`. The in-game options menu only
exposes a handful of indices; writing an index past what the UI offers (e.g. `24`) selects a higher
resolution the menu doesn't expose:

```python
p = ".../SAVE/CONFIG00.DAT"
b = bytearray(open(p, "rb").read())
b[0] = 24
open(p, "wb").write(b)
```

Confirmed working (reported by the user). The rest of this 177-byte file is unexplored.

## Wine/Wayland: keyboard not registering in-game

Likely cause: the game runs true fullscreen, which plays badly with a Wayland compositor's input
grab model. `pop3-rev/scripts/desk_wine.sh` already has the fix - it toggles Wine's "emulate a
virtual desktop" setting (`HKEY_CURRENT_USER\Software\Wine\Explorer`, `Desktop`=`Default` /
`Explorer\Desktops`, `Default`=`800x600`, see `export.reg`), which runs the game in an ordinary
windowed surface instead of exclusive fullscreen:

```
bash pop3-rev/scripts/desk_wine.sh 1   # enable (800x600 window)
bash pop3-rev/scripts/desk_wine.sh     # disable (back to fullscreen)
```

Confirmed working for the keyboard issue. If a compositor still misbehaves, the other lever is
forcing XWayland instead of Wine's native Wayland driver: `WAYLAND_DISPLAY= wine ...`.

## Live memory: fill every charge

All of these need the game running and a `sudo python3 <script>` (ptrace); `find_game()` below is
shared boilerplate (copied in each script rather than imported, so each is self-contained to hand
to the user).

```python
import os, struct, sys

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
```

### Relevant addresses (D3DPOPTB.EXE; `addrmap.py` translates for POPTB.EXE)

| Address | Field |
|---|---|
| `0x89C6F0` | player tribe index (`u8`) |
| `0x89D188` | turn counter (`u32`), +12/s while simulating, 0 if paused/in a menu |
| `0x89D1C8 + tribe*0xC65` | tribe record base |
| `+0x94D` | `bank` (`u32`), clamped to `MAX_MANA` (1 000 000) |
| `+0x951` | `reservoir` |
| `+0x955` | `incoming` (`u32`): mana earned this cycle, not yet distributed |
| `+0x959` | `needed` (`u32`): sum of `charge[spell]` over available spells |
| `+0x969 + 4*spell` | `charge[spell]` (`u32`, spells 1-21): mana still needed for that spell's *next* charge |
| `0x96070A + tribe*0x38` | `struct_56B` (56 bytes = 14 dwords, see "Open problems") |
| `+0x00` | learned-spell bitmask (`u32`?, width/polarity not confirmed live) |
| `+0x10` | blocked-spell bitmask (same caveat) |
| `+0x14 + spell` | charge byte (low nibble = charges, high nibble = gifted one-shots) - **did not visibly drive the panel** when poked directly this session, see below |

### What worked

Mana income is the real mechanism, and it's what actually moves the panel: write a huge `incoming`
for the player's tribe, and the game's own per-turn distribution (every 16 turns / 1.33 s) pays off
every learned, **unpaused** spell's `charge[spell]` for real, filling it up to its cap the normal
way (confirmed: user saw it work, and successfully cast a spell afterwards).

```python
TRIBE_BASE, INCOMING_OFF, PLAYER_TRIBE_ADDR = 0x89D1C8, 0x955, 0x89C6F0
pid, translate = find_game()
with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
    mem.seek(translate(PLAYER_TRIBE_ADDR)); tribe = mem.read(1)[0]
    addr = translate(TRIBE_BASE + tribe * 0xC65 + INCOMING_OFF)
    mem.seek(addr); mem.write(struct.pack("<I", 6_000_000))
```

Caveat the user hit: a newly-"known" spell (via the `.hdr` edit above) starts **paused** - the
in-game right-click-a-spell-icon "toggle charging" shortcut (shortcuts.md) must be used once per
spell before income reaches it at all (`spells.md`: "`charge(mana)` shares mana... between the
spells taking it (known, not full, **not paused**)"). Without that, `incoming` just piles up
unused.

### What didn't (reliably) work

- Writing `struct_56B`'s `+0x14+spell` charge byte directly: the panel kept showing 0 progress
  regardless, even though the byte itself stuck (re-read later and still held the written value) -
  whatever the panel actually reads is not simply this byte, or not only this byte.
- Clearing the blocked bitmask (`+0x10`) directly: worked once (spells castable right after), then
  the same spells were blocked again later without anything obvious re-triggering it from the
  user's side. Not root-caused. A continuously-running clear-loop (every ~1 s) is the pragmatic
  workaround while this stays unexplained:

  ```python
  # every ~1s: if struct_56B+0x10 != 0, zero it; if tribe.incoming < 500_000, top it back up to 6_000_000
  ```

### Open problems (not resolved this session)

- **`struct_56B` may be reloaded from the level file itself**, not just computed at runtime: a
  function Ghidra calls `load_level_4` (`0x410D80`) does `mov edi, 0x96070A; call 0x485E60; mov
  ecx, 0xE; rep movs dword es:[edi], ds:[esi]` - a 14-dword (56-byte, i.e. exactly `struct_56B`'s
  size) block copy *from the mapped level file* into this address. If the game re-runs this (or an
  equivalent per-tribe resync) at some point after load - plausible candidates: `0x4ECAC0`
  (`tribe_recount_and_mana_income`, "rebuilds unit lists, income") or a scripted/periodic event -
  that would explain "the unblock worked once, but not anymore": the live clear gets stomped by a
  fresh copy from the level's own on-disk data, which (unlike the `.hdr`'s `SpellsAvailable`) was
  never patched. **Not confirmed**: no caller of `0x410D80` was found by a direct `call` search (it
  may be reached through a function-pointer table, like the per-thing-type level loaders
  level-format.md describes - thing type 4 is "vehicle", so this name may also simply be wrong, per
  the usual Ghidra-naming caveat). Whether this struct's on-disk source lives in the level's `.dat`
  and at what offset is untraced; finding it (or disproving the resync theory with a live watch
  across a cast attempt) is the next step.
- Whether `+0x14+spell`'s charge byte is read by the UI at all, and if not, what is, is unresolved.
- A `watch_cast.py`-style poll (print `bank`/`incoming`/a spell's charge byte/blocked bit only on
  change, at ~5 Hz, while the user attempts a cast) was set up to settle whether a cast attempt even
  touches this data - result pending.

## Scripts this session (scratchpad, not preserved across sessions)

Written to `/tmp/claude-1000/-home-laurent-compile-pop3-rev/<session>/scratchpad/`: `max_charges.py`
(the `struct_56B` poke that didn't stick), `max_charges2.py`/`unblock.py` (the `incoming`/`blocked`
pokes that did, transiently), `diag.py`/`diag2.py` (read-only state dumps), `watch_unblock.py`
(continuous re-clear loop), `watch_cast.py` (poll during a live cast attempt). Scratchpad paths are
session-specific and get cleaned up; the snippets above are the parts worth keeping.

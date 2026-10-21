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

## Live memory: measuring a Blast (read-only)

Goal: check pop3-rev-analysis.md's "Blast push and flight" hand estimates ("not measured") against
the real game, by watching a pushed person's position/velocity/life turn by turn - same
`find_game()`/`/proc/pid/mem` approach as above, but read-only (no `sudo` write needed, though
`ptrace` read still needs it in practice) and synced to the turn counter (`0x89D188`) rather than
wall-clock polling, since turns run at ~12/s and polling on a fixed sleep risks missing or
double-counting one. Script: `pop3-rev/scripts/measure_blast.py` (kept, unlike the rest of this
doc's scratch snippets, since it's read-only and reusable for the next trial).

### Unit record (confirmed live this session)
`unit_array` 0x8E0428, 0xB3 bytes/record, 2000 slots. Shared by every unit class (person, effect,
etc. - `unit_class` +0x2A picks the interpretation):
- `flags` +0xC (u32): bit `0x2000` airborne, bit `0x80000` blown (set by a blast push).
- `pos` (6 bytes, confirmed from the person physics step's disassembly, 0x4e6d1d-0x4e6d7b): `x`
  (i16, low word of the dword at +0x3D), `z` (i16, high word of that dword, i.e. +0x3F), `height`
  (i16, +0x41) - same x/z-packed-plus-height convention as the tribe's reincarnation site
  (+0x911/+0x915). A live blown unit's `height` moves by exactly its `vel.y` every turn, `x`/`z` by
  `vel.x`/`vel.z` - clean confirmation. Six bytes follow (+0x43-+0x48, before velocity at +0x49)
  that tracked the same values as velocity in one trial; not explained, not needed for this.
- `vel` (as already documented): `x` +0x49, vertical +0x4B, `z` +0x4D, each i16.
- `life`/`max_life`: u16 at +0x6E/+0x6C.
- For the blast effect itself (not the person it pushes): `unit_class` +0x2A == 7 (effect),
  `state` +0x2C == 1 (simple blast); same `pos` fields give its centre, to compute the real
  distance `d` to a pushed person.

### What's confirmed
Scanning the pool each turn for `unit_class == 1` and `flags & 0x80000` and logging `pos`/`vel`/
`life`: vertical velocity drops by exactly **-32/turn** (matches "Gravity 32 per turn" exactly);
horizontal velocity (`x` and `z`) each drop by exactly **-2/turn** while airborne (matches "Air
drag 2 per turn"); landing is visible as a sharp jump in horizontal velocity (friction) and
`height` clamping instead of continuing its fall. All of this matches "Person physics" exactly,
live, across both a short single push and longer multi-turn flights.

Session 2026-10-21 (4 trials, 7 pushed persons, ~100 logged turns): the same two numbers (-32,
-2) hold with **zero exceptions** across every trial while airborne, and are independently
confirmed from the EXE on disk - no running game needed - by reading the movement-profile table
(`0x5A7B90`, 26 bytes/row, "Walking speed"/"Unit record"): row 2 (brave, per
pop3-rev-analysis.md's own "profile 2" note) is `(256, 170, 64, 110, 192, 512, 192, 512, 384, 32,
28, 72, 1)` - word 9 (+0x12) = **32** (gravity), word 10 (+0x14) = **28** (ground friction), words
4/6 (+0x8/+0xC) = **192** (horizontal velocity cap, both axes) - all matching "Person physics"
exactly (`scripts/measure_blast.py`'s own docstring has the one-liner to reproduce this read).

One live reading looked like a mismatch and turned out not to be: two different persons in the
same trial both saturated their horizontal velocity at exactly **-190**, not -192. Resolved by
the table confirmation above, not a correction: the push, its 192 clamp, and that same turn's -2
air drag all happen before the turn ends, so the earliest sample this script can ever read back
is already `192 - 2 = 190` - the uncapped/undragged value is never actually observable this way.
This is the general shape of the problem below.

Session 2026-10-21, second trial (`blast_log2.csv`, a real multi-unit skirmish rather than a clean
isolated cast, 10 persons, ~200 logged rows): closes the -190/-192 question for good - the same
cap is seen **untouched** this time (two units, vel_x = 192 and vel_z = 192 on different axes,
before that turn's drag brought them to 189/190 the next sample). It also directly confirms two
numbers from "Blast push and flight"/"Person physics" that v1 couldn't reach, because this time
several persons stayed blown across more than one of the blast's own turns, so the damage ticks
landed inside the logged window instead of before it:
- **`BLAST_DAMAGE_PERSON` = exactly -50** life, 5 separate turns across 3 persons - including while
  still rising (vel.y > 0), not just once grounded.
- **`FALL_OUT_OF_WW_DAMAGE` = exactly -700** life, 3 separate landings (persons 1666, 1694, 1320) -
  applied the turn *after* `height` first reaches the ground, not the same turn.

### Still open
The distance-dependent part of "Blast push and flight" itself (`f = (R - d) / R`, the slope rule,
the 3-turn cumulative push) is still not checked. What's missing is specifically the *first*
tick that turns a standing person into a blown one - the sustained direct-damage/fall-damage
ticks above are visible precisely because they land while a person is already blown, but:
- the first blown sample is already after that turn's full push-and-physics update (see the
  -190/-192 case above), so it never shows the raw, pre-clamp push;
- a person pushed on more than one of the blast's 3 ticks has already moved between ticks, so its
  position at first sample is not its distance `d` *at cast time* - back-computing `d` from where
  we first see it systematically overstates the real distance, which made an early by-hand fit of
  the formula look like it needed a "double push" when it didn't;
- the very first `BLAST_DAMAGE_PERSON` tick, the one dealt before the person is pushed hard enough
  to fly, is still invisible to a blown-only filter.

v2 of `measure_blast.py` logs every person every turn unconditionally (not just blown ones), which
fixes all three - but **a running Python process doesn't pick up an on-disk script edit**: the
second trial above was still produced by v1 (it has zero not-blown rows), almost certainly because
the logger had already been started before the v2 edit landed. Next step: kill and restart the
logger fresh, ideally against one isolated unit rather than a live skirmish, at several known
distances/slopes, joining `kind=blast`/`kind=person` rows on `turn` to fit the formula.

## Scripts this session (scratchpad, not preserved across sessions)

Written to `/tmp/claude-1000/-home-laurent-compile-pop3-rev/<session>/scratchpad/`: `max_charges.py`
(the `struct_56B` poke that didn't stick), `max_charges2.py`/`unblock.py` (the `incoming`/`blocked`
pokes that did, transiently), `diag.py`/`diag2.py` (read-only state dumps), `watch_unblock.py`
(continuous re-clear loop), `watch_cast.py` (poll during a live cast attempt). Scratchpad paths are
session-specific and get cleaned up; the snippets above are the parts worth keeping.

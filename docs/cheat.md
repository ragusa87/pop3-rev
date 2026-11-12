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

## Hidden developer settings menu (BYRNE cheat + hold O)

Not a file/memory edit - a feature already built into the game, reachable with only the keyboard.
Source: [`ystartgo/Populous_3_Tool`](https://github.com/ystartgo/Populous_3_Tool) (third-party,
player-discovered); this session cross-checked it against `D3DPOPTB.EXE`'s own disassembly (see
`commands.tsv`'s `tribe_cmd 0x17` row and `functions.tsv`'s `0x443520` row for the full static
trace) and found a strong, consistent match - treat the exact item *names* below as that
third-party's testimony, not independently read from the game (the actual strings live in a
runtime-only table this session couldn't read statically; see "Open problems" at the end of this
section for how a future live session could confirm them directly).

**They're hidden developer settings left in the game, which you can change once cheat mode is
on.** To use them: turn on cheats (`Tab+F11`, type `BYRNE`, press Enter), then hold the `O` key.
While holding it, use `↑`/`↓` to scroll through the settings and `←`/`→` to change the selected
one.

Most of the ~72-76 entries (this session's own static count of the exe's table found 76; the
source above describes about 72 - possibly a different game build, or a few the source didn't list
individually) are technical switches the developers used for testing, such as turning off texture
drawing, sync checks, or pathfinding ("jnav"/"jav") values. These are the ones a regular player (or
`open-populous`) is most likely to care about. The number is the 1-based position you'd reach by
holding `O` and pressing `↓` that many times from the first entry - this session confirmed it lines
up exactly with 1 + the 0-based record index in the exe's own `0x5a8ab8` table (`commands.tsv`'s
own per-item breakdown), and several of these specific matches are corroborated by a real,
non-null "apply" callback firing exactly where you'd expect one (texture mode, AI on/off, fog of
war, auto-vehicles, the attack-area overlay, flip rotation all have one; a plain visual toggle like
sky/sea/lens-flare correctly has none):

- **Gameplay**: Fog of war (48), Computer Player off (29, turns off the enemy AI), Auto use
  vehicles (49), Maintain minimum population (50), Human shaman omnipresence (66), Autocast spell
  (68)
- **Controls and camera**: Camera Zoom on (40), Flip Rotation (70), Swap Rotate/Move (72), Auto
  Deselect (71), Continuous raise/lower (51, for terrain)
- **Visuals**: Sky On (21), Sea On (43), Lens Flare (64), Animating Water (25), Footsteps (24), Use
  32x32 Hires Textures (23)
- **Info overlays**: Show attack areas (57), Show flat areas darkened (55, shows ground you can
  build on)
- **Fun**: Island Level (44) raises or lowers the sea level

A word of caution: many of the remaining options (like No Draw, No poly draw, or the sync checks)
can blank the screen or make the game unstable. If something goes wrong, set the option back or
restart the level.

**Open problems** (worth a future live session): read the runtime string table at `0x972ba8` while
the menu is open to get the literal name text for all 76 entries directly from the game instead of
via the third-party source above; confirm the exact `O`+arrow-key input remap this session didn't
trace (likely rerouting the normal camera-scroll arrow keys into the `ui_cmd 0x49`-`0x4e` stepper
cluster while `O` is held); and resolve the 72-vs-76 count discrepancy (could just confirm this
session's build has 4 extra entries past what the source's build/version had).

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
the logger had already been started before the v2 edit landed.

### Session 2026-10-21, third trial (`blast_log3.csv`, v2, 192 persons, ~165k rows)
A genuine restart of the logger, so it actually ran v2 this time. Live gameplay (a real skirmish, not
an isolated staged trial), 14 separate Blast casts caught cleanly (3-row `kind=blast` clusters each).
For every nearby person, this is the first time a *pre-cast* position/velocity/life sample exists, so
the push itself could finally be checked:

- **New timing fact, not previously documented here**: a pushed person's position and velocity stay
  completely frozen through the blast's own 3 active turns - even one sitting exactly at the impact
  point the whole time shows zero change - and only jump on the turn *right after* the blast effect
  itself disappears. The engine commits the push (and the blown flags) as a single step once the
  effect ends, not incrementally per tick; that single jump already reflects whatever accumulated
  internally.
- **Push direction**: comparing each person's pre-cast position (relative to the blast centre) against
  its post-jump velocity direction, across ~15 clean detections the push points outward from the
  centre to within 0-10° - confirms "angle = direction from the centre to the unit, no randomness"
  exactly.
- **Push magnitude**: plausible, not pinned down. Horizontal push vs. predicted `140 × f` ranges
  0.9x-2.3x across detections - inside the slope rule's own documented range (x1.06 flat, up to x2
  falling-away), consistent but not provable without also logging ground height. Vertical push vs.
  predicted `98 × f`, in the cleanest same-spot (`f = 1`) cases, clusters at two repeating values 98
  apart rather than one smooth value - a real, reproducible pattern, left unexplained.

Next step for an exact fit: a controlled single-unit flat-ground trial (now that v2 actually captures
pre-cast state), ideally also reading the unit's local ground height each turn to separate the slope
rule from the base coefficient.

### Session 2026-10-21, fourth trial (`blast_log4.csv`) - the controlled trial, plus a disassembly find
A genuinely clean trial this time: 15 units, flat ground (height 128 at every impact point), 3 casts,
every turn logged (0-340, no gaps). Re-running the same pre-cast/post-jump analysis on it:

- **Horizontal `140 × f` confirmed tightly on flat ground**: the cleanest single-push detections (angle
  matched to within 0-1°) land at ratio 0.97-1.04 against `140 × f` - essentially exact, with the small
  excess consistent with the slope rule's own flat-ground floor (×1.0625 from `clamp(0,1,16)/16`).
  Detections at ~2.0-2.1x are consistent with the same person qualifying for two of the blast's three
  ticks (the doc's own "cumulative... pushed again" - see below for why that's now better understood).
- **Vertical: measured `132`, not `98`, at `f = 1` - reproduced exactly across two independent sessions**
  (this trial and the third one, different persons, different casts): a person sitting exactly at the
  impact point gets a `+132` vertical kick, not `+98`. Away from `f = 1` the vertical readings get
  noisy (one unit's vel.y oscillates on its own, unrelated to any blast, between 0 and -64 - a false
  detection to watch for), so `132` at `f=1` is the one number here that's both clean and reproduced.
- **Horizontal and vertical don't scale together on a "double hit"**: the ~2x horizontal cases above
  still show roughly 1x vertical, at first looking contradictory. It isn't - see the disassembly below:
  the slope rule only multiplies the horizontal `len`, never the vertical term, so a bigger slope
  multiplier (not a second hit) can easily explain a 2x horizontal ratio with an unchanged vertical one.

**Disassembly of the push itself** (reached from the shared simple-blast turn handler `0x50b740`,
traced this session): at `0x50b9a6`-`0x50b9bf` it computes `d` via `call 0x4503f0` (distance, matches
the doc's own citation) between the blast's position (`edi+0x3d`) and the candidate person's
(`esi+0x3d`), where `edi` is the blast instance and `esi` the person being considered. Then, at
`0x50b9ca`-`0x50b9d2`: `ebp = clamp(d, 0, R)` where **`R` is read from `DWORD [edi+0x6c]`** - the
same field the doc already calls "radius", not a hardcoded `1280`. At `0x50b9d8`-`0x50b9ec`:
`eax = movsx WORD [edi+0x74]` (a per-instance i16, the "140" from the doc) `* (R - d) / R`, then
`call 0x4e93f0` with `(len, &blast_pos, &person_vel)` - this is the slope-rule-and-apply routine,
writing the adjusted push straight into the person's `vel.x`/`vel.z` (`esi+0x49`). At `0x50b9f4`-
`0x50ba05`: the same `(R - d) / R` again times **`movsx WORD [edi+0x78]`** (the "98"), added directly
to `vel.y` (`esi+0x4b`) with a plain `add`, no slope call - confirms the slope rule is horizontal-only.

**The upshot: "140", "98" and "R" are not universal constants baked into this code - they're fields on
the blast instance itself, set by whichever spell created it** (Blast, Firestorm's fireball, Volcano's).
`measure_blast.py` v3 now reads `+0x6c`/`+0x74`/`+0x78` straight off the `kind=blast` row every turn, so
the next trial gets the exact ground truth directly instead of inferring it from a person's velocity
delta under an assumed `R`. (98/140 ARE confirmed real values elsewhere in the doc, just for a different
caller: a destroyed boat's land explosion passes `0x50B6F0` the literal params `3, 2, 5, 0x62, 0x8C, 1, 0` -
`0x62`/`0x8C` = 98/140 decimal. So the "132" measured live for the Blast spell's own cast is a different
call site genuinely configured differently, not a doc error.)

### Landing in water: a person drowns, confirmed 3 times
Both `blast_log3.csv` and `blast_log4.csv` had a pushed person's flight end over water. All three instances
(persons 1827, 1831 in the fourth trial; 1272 in the third) show the identical sequence:
1. Ordinary blown flight (gravity -32/turn, drag -2/turn, as established) until `height` reaches the water
   surface (`0`, locally).
2. One turn later, flags +0xC bit `0x80000` (blown) clears, and a sinking sub-state kicks in: flags gain
   bits `0x2`, `0x10000`, `0x100000`, `0x40000000`.
3. `height` now drops by a **fixed -16/turn for exactly 16 turns**, regardless of the unit's actual stored
   velocity (which stays frozen, unused) - identical in all 3 instances, down to the exact turn count.
4. At `height = -256`, life is forced to **exactly 0** (a clean kill, not a subtraction) and flag bit `0x2`
   clears again.

Independent of this: the ordinary hard-landing fall damage (`FALL_OUT_OF_WW_DAMAGE` 700, needs vel.y ≤ -200
the turn `height` first hits 0) can also apply on the way in - person 1827 took both (-700, then drowned 17
turns later); 1831 and 1272 touched down too gently for that (vel.y -188 both times, below the -200
trigger) but still drowned on the same schedule regardless - drowning here looks unconditional on impact
speed, unlike the fall damage. Bit `0x2` very likely exists to exempt a sinking unit from the OTHER,
generic per-turn drowning check ("Drowning") while its own dedicated sink-and-die sequence runs - that
other check's own "not drowning if bit 0x2" reads backwards until you realize it means "already handled
elsewhere," not "safe."

## RESOLVED (live session, game now available in-container): the Reincarnation Centre's 8 pillars rise STAGGERED, not together - the static trace was wrong, or incomplete

The dispute above is settled in the user's favour. Live poll (`scripts/watch_pillars.py`, run via
the Docker rig - see "Docker headless rig" below - against a freshly-loaded level 1, launched
straight into via the `-LEVEL 1` command-line switch to skip menu/FMV nondeterminism) of the local
tribe's 8-entry pillar-slot array (`tribe_struct+0xA0D`) and each resolved pillar's own `+0x2C`
state / `+0x41` height (i16), polled every 0.02s (turns run ~12/s, so several samples per turn):

```
turn=37 slot7 spawns (id=1626), height=-112
turn=40 slot6 spawns (id=1550), height=-112   (slot7 already at -64, 3 turns into its own rise)
turn=41 slot5 spawns (id=1498), height=-112
turn=44 slot4 spawns (id=1662), height=-112
turn=45 slot3 spawns (id=1686), height=-112
turn=48 slot2 spawns (id=1602), height=-154
turn=49 slot1 spawns (id=1528), height=-112
turn=52 slot0 spawns (id=1736), height=-148
```

Each pillar's own height then climbs independently (consistent with the static trace's "+16/turn
for 16 turns" once it has spawned) - confirmed NOT in lockstep: at any given turn in this window,
up to 3 different pillars are mid-rise at 3 different heights simultaneously, visibly staggered.
Net: **spawn order is slot 7 down to slot 0 (reverse of what a naive "loop 0..7" read would
predict), arriving at intervals that alternate +3/+1 turns (37, 40, 41, 44, 45, 48, 49, 52) - total
span 15 turns (~1.25s) for all 8 to start**, not "all in the same tick" as `0x41c140`'s static
trace (`docs/functions.tsv`) concluded. Screenshot at turn 77 (a scripted tutorial pause a few
turns after the last pillar finished) visually confirms a fully-formed, normal-looking stone
circle, consistent with the player-facing effect being "they all rise close together" even though
they demonstrably do not start in the same tick.

**RE-TRACED, a later static session: `0x41c140` itself was never the function that ran.** Re-read
it instruction-by-instruction - it is exactly what the prior static trace said (a single
uninterrupted loop, all 8 pillars in one tick, no delay mechanism anywhere in it) - but it
unconditionally sets global `0x89D17C` bit `0x20` as its very first action on any real run, and
nothing in the exe clears that bit except its own sibling `0x41C520`'s very end. Since the bit
stayed clear through the entire live-observed window (turn 0 through 61, polled continuously),
`0x41c140` provably never executed during that playthrough - "contradicted by live data" was really
"wrong function identified," not an error in reading `0x41c140`.

The real mechanism, found by following the live data instead: class-7 effect **TYPE 7**'s own init
(`0x50C690`, already named `move_rs_pillar`/"move rs pillar" by an earlier session that had
correctly read its queue-based, one-slot-at-a-time replace logic but hadn't yet connected it to
level-start, having filed it as "maintenance/relocation, not part of the intro" - that call is now
withdrawn) pops ONE pending `(slot, x, z)` job off the generic scratch stack `0x892443` per spawn
and places/replaces exactly one of the 8 pillars - a genuinely staggered, re-triggerable mechanism,
unlike `0x41c140`'s own tight loop. **Still open**: who spawns these type-7 effects one at a time,
1-3 turns apart, matching the observed 37/40/41/44/45/48/49/52 sequence, and who pushes the 8
matching jobs onto the scratch stack beforehand - no literal `push 0x7`/`push 0x7` (type/class) call
site exists anywhere in the exe for this, so the type is computed in a register at every real call
site, same as the Angel-of-Death statue's own register-typed spawn (AGENTS.md's own cited
precedent).

**Lead chased, same session - dead end, but narrowed the search**: `SET_REINCARNATION`'s native
`interpret_script` opcode handler was found (`0x48DC26`, case 0x88 of dispatch `switchD_0048cc8d` -
`ai-scripts.md`'s id 1164 confirmed real: `1164-0x404=0x88`, matches exactly). Its ON-case only
sets a land-reservation bit (`tribe+0x93D` bit `0x10000`) and calls `0x44FF80`, which computes the
site's 8 ring cells + center and stamps/claims them in the map's 0x4000-entry land-zone table
(`0x8A03E4`), additionally directional-searching and flattening ground for the human tribe
(`0x450610` mode 3/4, destroys blocking scenery per cell). **Neither function ever touches the
pillar-queue stack `0x892443` or calls `alloc_unit` with a type-7 effect** - so `SET_REINCARNATION`
reserves/flattens the land but does not itself spawn pillars.

**FULLY RESOLVED, same session, by live-verifying the `SET_REINCARNATION` dead end and then reading
`0x41c140`'s own call site (`load_level`) in full.** `scripts/watch_rc_flags.py` (new, committed)
polled `tribe+0x93D` alongside the pillar array on a fresh `-LEVEL 1` load: `SET_REINCARNATION`'s own
bit `0x10000` never fired (confirming the dead end live, not just statically), but bit `0` (the
"prepare rs land" ground-flatten effect's own busy flag, see below) went high at turn 14 and low at
turn 35 - almost exactly the first pillar's turn-37 appearance, 2 turns later. That timing match was
the thread that unravelled the whole mechanism:

- `load_level` calls `0x41C140` only when `BYTE[ds:0x89C661] bit 0x8 AND BYTE[ds:0x89B7A3] bit 0x8`
  are BOTH set (`0x42B501`-`0x42B513`) - an alternate/rarer path, neither bit set in the observed
  session, which is why it never ran.
- The ORDINARY path, a few instructions earlier in the SAME function and reached unconditionally for
  every active tribe (`0x42B446`-`0x42B47F`): `set_tribe_start_pos` (`0x419790`) -> `clear_tribe_1`
  (`0x419810` - derives the RC anchor from the shaman's own position, calls `0x44FF80` to reserve its
  land) -> `process_tribe_1` (`0x419880` - issues the shaman **order-kind 18**, `order_execute`'s own
  dispatch table `0x432D18`, previously flagged "not traced").
- Order-kind 18's handler (`0x433A10`, newly traced) is the shaman's own 4-state "(re)build the RC"
  task: states 0-1 walk to the site; **state 2** box-clears the ground and spawns the **"prepare rs
  land" effect** (class 7 type 8, `0x50C780`/`0x50C840`) - its ~20-tick run is exactly `tribe+0x93D`
  bit 0's observed turn 14-34/35 window; **state 3**, once the ground-flatten finishes, fires one
  **`class-8/type-1` "standard shot" projectile per pillar slot**, a tick apart, each carrying a
  generic impact-spec (`+0x7C=7`/`+0x7D=7`/`+0x80=`slot/`+0x82,0x84=`target position).
- The shot's own arrival triggers the GENERIC class-8 impact handler `0x4BB290` (shared by every shot
  in the game - fireballs, volcano shots, etc., each with their OWN different impact-spec), which
  stages `(slot, x, z)` onto the scratch stack `0x892443` and spawns `alloc_unit(class=7, type=7)` -
  landing in `0x50C690`'s already-documented "move rs pillar" slot-replace logic.
- Each shot's own flight time (varying by distance from the shaman to each of the 8 ring slots) is
  exactly what produces the observed staggered 1-3-tick gaps between pillar appearances - no
  per-turn poller, no hidden scheduler, just ordinary projectile travel time.

Net: `0x41c140`'s own code was correct and unchanged throughout this whole investigation; it's simply
the alternate/rarer of two level-load paths, and the ordinary one (`process_tribe_1` -> shaman order
18 -> shots -> generic shot-impact handler) is what actually builds the Reincarnation Centre on a
normal level load. Full write-up: `docs/functions.tsv` rows `0x41c140`/`0x50c690`/`0x432d18`/`0x4bb290`
(all extended), new rows `0x48dc26`, `0x44ff80`, `0x450610`, `0x419790`, `0x419810`, `0x419880`,
`0x433a10`.

**Tool**: `scripts/watch_pillars.py` (committed, reusable) - run via
`scripts/docker/capture.sh scripts/watch_pillars.py --every 0.02` inside the Docker rig (see
"Docker headless rig" below), started before the level loads (it retries `find_game()` until the
process appears, then logs unconditionally from turn 0). Resolves each pillar's thing-id through
the generic id->pointer table confirmed in `dis.txt` as `mov reg, DWORD PTR [reg*4+0x890390]`
(a flat array of live runtime pointers, one per thing-id, not a stride-based index into
`unit_array` - worth noting generically, this wasn't spelled out this precisely before).

## Docker headless rig (new this session - the game is now runnable in-container, not just inspectable live by the user)

A full headless Wine + Xvfb + x11vnc + openbox rig already exists (`docker-compose.yml`,
`docker/Dockerfile`, `docker/entrypoint.sh`, `scripts/docker/*.sh`) - `cap_add: SYS_PTRACE` gives
root-inside-container real ptrace access to `/proc/<pid>/mem`, no host `sudo` prompt needed.
Previously documented as existing (`docs/camera.md`) but this session is the first to actually
drive it end-to-end for a new investigation:

- `docker compose up -d` (from the repo root) starts it; `docker compose ps -a` to check state -
  if a stopped container shows `Exited (1)` on restart, it's almost always a stale
  `/tmp/.X99-lock` left in its writable layer from a prior run ending uncleanly; `docker compose rm
  -f pop3 && docker compose up -d` clears it (safe - the Wine prefix and this repo are both
  separately bind-mounted, nothing is lost).
- **Mouse-cursor relative-mode drift (the game's own rendered cursor position silently decoupling from the
  real X11 pointer position `xdotool` controls, making precision clicks on small HUD icons unreliable or
  impossible) is a known, GENERAL issue with this game/engine - not specific to this Docker rig, Xvfb, or
  headless setups.** It happens outside Docker too, on Wayland or with multiple displays. **The reliable fix
  is a game restart** (kill wine, relaunch), not trying to re-calibrate an already-drifted session via more
  mouse moves - confirmed after two separate live sessions each burned significant budget fighting this
  before learning the fix. Restart BEFORE attempting any precision click, not after the drift is already
  causing problems.
- `scripts/docker/launch_game.sh` / `start_level1.sh` launch the exe. **The main menu's
  highlighted/default item is NOT reliably "NOUVELLE PARTIE"** even on a cold wine process - it
  persists the last-used item across full process restarts (some menu-state file in the shared,
  host-bind-mounted Wine prefix), so a fresh container can land on e.g. "MULTIJOUEUR" instead.
  Don't assume the documented key sequence's defaults still hold; screenshot
  (`docker compose exec pop3 bash -c "import -display :99 -window root /tmp/x.png"` then
  `docker cp` it out) to check the actual highlighted item before pressing Return.
- **"Tight-loop key presses drop a third to half of them" (this doc's own earlier claim) could not
  be reproduced in a later, much more rigorous session** - ~10 trials of `xdotool key Up`/`Down`
  against the in-level pause menu's 7-item list, varying delay from 1.5s down to 1ms between
  presses (individual `docker compose exec` calls, a single `bash -c` shell `for` loop, and
  `xdotool key --repeat N --delay D` with no process-spawn overhead at all) all landed on the
  exact expected item, every time but one. **Found instead: this menu's Up/Down focus cycle is
  CIRCULAR over 8 stops** (the 7 visible items plus "RETOUR" below them - wraps from the last
  item to "RETOUR" to the first item and back, confirmed with a 5-press batch landing exactly at
  `(start - 5) mod 8`) - a prior session assuming simple clamping at the list's ends would
  misread a wrapped result as "missing" presses, which may explain some or all of the originally
  reported drops without any real input-reliability problem. **One anomaly did occur once** (3
  `Up` presses at 1.5s from "OPTIONS" landed 2 steps in the WRONG direction instead of 3 steps
  up) and was never reproduced despite many follow-up attempts with the same timing - possibly
  specific to the first keypress right after a menu first opens/gains focus, but a repeat of
  that exact scenario (close pause menu, reopen, immediately send presses) landed in a different,
  confounding "NIVEAU RATE" (level failed)/Escape-toggle state instead of a clean reopen, so this
  was not conclusively isolated. **Net practical guidance, updated**: single presses with a
  screenshot to confirm are still the safest default, but don't assume a batch's "wrong" landing
  spot means dropped keys before checking whether the control simply wraps around - and a single
  unreproduced miss doesn't mean every batch needs re-verifying one key at a time.
- **Simplest fix, once found this session: the exe takes an undocumented `-LEVEL N` command-line
  switch** (confirmed via `strings D3DPOPTB.EXE`, alongside the already-known `-allres` etc.) -
  `wine D3DPOPTB.EXE -allres -LEVEL 1` skips straight to the level-select star map with that level
  already focused (one `Return` away from actually loading it), bypassing the unreliable menu
  navigation above entirely and making repeated fresh-level captures deterministic. Still shows the
  Bullfrog/EA legal splash first (any keypress dismisses it).
- The in-level tutorial (level 1) pauses the simulation turn counter (`0x89D188`, confirmed static
  while a modal dialog is up) on scripted checkpoints (e.g. "I've built my reincarnation site..." at
  turn 77 in this session's run) - if a poll looks "stuck," check for a dialog via screenshot before
  assuming the poller is broken.
- Screenshot recipe: `docker compose exec pop3 bash -c "import -display :99 -window root
  /tmp/x.png"` (ImageMagick, already in the image) then `docker cp pop3-rev-pop3-1:/tmp/x.png
  <local path>` - the container's `$DISPLAY` is `:99`, not the host's.

## Scripts this session (scratchpad, not preserved across sessions)

Written to `/tmp/claude-1000/-home-laurent-compile-pop3-rev/<session>/scratchpad/`: `max_charges.py`
(the `struct_56B` poke that didn't stick), `max_charges2.py`/`unblock.py` (the `incoming`/`blocked`
pokes that did, transiently), `diag.py`/`diag2.py` (read-only state dumps), `watch_unblock.py`
(continuous re-clear loop), `watch_cast.py` (poll during a live cast attempt). Scratchpad paths are
session-specific and get cleaned up; the snippets above are the parts worth keeping.

## `process_cmd` breakpoint method: Escape confirmed as `ui_cmd 0x9b`, and a likely resolution of the long-chased Space/alarm mystery (later session, 2026-11-08)

Picking up `docs/trace-backlog.md`'s own "a live memory check is very likely faster than continuing
static analysis" recommendation for the unresolved "Space: bell alarm" keybind - this session set up
the Docker rig fresh (`game/D3DPOPTB.EXE` wasn't present; copied in from the host's own
`~/.wine/drive_c/Program Files (x86)/Bullfrog/.../D3DPOPTB.EXE`, sha256 `3a5065c7...` - matches
AGENTS.md's second known-good build) and drove it to a running level 1 (`start_level1.sh`'s own fixed
sleeps weren't enough this run - needed 4 Escapes, not the scripted 1, to clear a longer intro FMV;
screenshot-and-adjust, as the script's own comments already warn).

**Method - a GDB hardware-breakpoint-free software breakpoint at `process_cmd`'s own argument load,
NOT a watchpoint on a global**: `process_cmd`/`0x4AAB80`'s raw `ui_cmd` id argument is loaded into
`ebx` at `0x4AAB9A` (`mov ebx,[esp+0x350]`); breaking one instruction later, at `0x4AABA1`, catches
`ebx` already populated on EVERY call to `process_cmd`, for ANY key/command, before any dispatch -
far more direct than guessing which global a given keybind's handler might write. `docker compose exec
-u root pop3 gdb -q -nx`, scripted via a short Python wrapper (attach, `break *0x4aaba1`, a `commands`
block that `printf`s `$ebx` and auto-`continue`s), run interactively (not `-batch`) so the wrapper can
send `SIGINT` to GDB itself (not the tracee) after sending test keys via `xdotool`, then
`delete breakpoints`/`detach`/`quit` cleanly from the resulting prompt.

**Result**: pressing **Escape** - both inside the tutorial's own modal "OK" dialog and in plain
gameplay with no dialog up - hits the breakpoint with **`CMD raw_id=0x9b`**, live-confirming
`commands.tsv`'s existing `ui_cmd 0x9b` row (previously only "named," flagged as an open question
whether it's a real second entry into the cancel/close state machine `0x9c`'s row already documents).
This is the first live (not purely static) keybind confirmation in this catalog's history - worth
updating `commands.tsv`'s own `input` column for `0x9b` to `Escape (live-confirmed)`.

**Initial attempt made it look like a much bigger blocker than Space alone**: `b`/`space`/`g`/`Tab`/
`Return`-in-gameplay/`p`, sent via both `xdotool key` and held `keydown`/`keyup`, first produced ZERO
breakpoint hits, while Escape and dialog-Return worked every time. **User correction: this is a focus
problem, not a broken input path - keep the game window focused the whole time, not just activated
once.** That was the key: the active window (checked via `xdotool getactivewindow getwindowname`) kept
reading back as `Wine Desktop` (the real top-level X window in Wine's virtual-desktop mode; "Populous,
The Beginning", id `23068687`, is a child of it, not independently focusable via `xdotool
windowactivate`/`windowfocus` - those calls report success but don't stick). Minimizing OTHER X11
interactions between focus being naturally correct (right after live menu/dialog navigation, which
inherently proves input is reaching the game) and sending the test key - no screenshots, no window
queries in between - made `b` reliably produce **`ebx=0xbf`**, confirming the long-standing static
guess for shortcuts.md's "B: help the tower" keybind, live, for the first time. A background loop
calling `xdotool windowactivate`/`windowfocus` continuously on the CHILD window id did NOT help and if
anything made things worse (every single key dropped while it ran) - likely fighting Wine's own
internal focus bookkeeping rather than helping it. **Net practical recipe**: do the minimum number of
X11 calls between a known-good input moment (menu/dialog navigation) and the test keypress; avoid
touching window focus explicitly on the child id at all.

Even with that fixed, delivery stayed flaky - consistent with this repo's older finding ("Docker
headless rig" above) that `xdotool key Down`/`Up` bursts silently drop a third to half their presses;
isolated single keys here had a roughly 1-in-4-to-5 hit rate, not 100%. A big WIN from this, though:
during one interleaved `b`/`space`/`b`/`space` run, ONE hit came back as **`ebx=0x59`** - a raw id
`commands.tsv` had never seen before. Resolved its handler address with the exe-raw-byte-table method
(`docs/trace-backlog.md`'s own "Notifications" section documents the technique) without needing
another live session: `0x59` -> `0x4AABD1` (the shared fallthrough shim) -> second table -> **`0x4ABD0D`**.
Static tracing of that handler (and its callees) turned up a complete, previously uncatalogued
mechanism - see `docs/functions.tsv` (`0x4da2a0`/`0x4f0e00`/`0x417ca0`/`0x417d80`/`0x4abd0d`) and
`docs/commands.tsv` (`ui_cmd 0x59`) for the full write-up: a per-person per-turn detector
(`0x4DA2A0`) stages "a hostile is threatening one of my people, here's where" into three new globals
(`0x8922DC`/`0x89C6A5`/`0x89C6A1`); a per-turn validator (`0x4F0E00`, called from `main_loop_inner`
right next to the already-documented fight-notification writes) expires it and periodically plays
**sound `0x23`** while it's live (very plausibly the actual alarm sound); and `0x4ABD0D` - `ui_cmd
0x59`'s own handler - consumes the staged position and jumps the camera there via a newly-traced
camera-recenter pipeline. This is the most complete, best-corroborated candidate yet for the
long-chased "Space: camera to the tower/fight under attack" keybind - though the live key-binding
itself is PROBABLE rather than certain (one hit, in an interleaved test, never cleanly reproduced in
isolation - `b` was tested 11 times total and never once produced `0x59`, making it the more
parsimonious source, but a cleaner reproduction - ideally with a real pending in-game attack - would
settle it definitively). The earlier "arrow key pans the camera" read from an even earlier session may
still be a false positive (a scripted tutorial camera move coincident with the keypress) - not
re-checked this session, now a lower priority given the focus fix above would make it easy to re-test
cleanly.

**Hazard found the hard way, three times: do NOT let this GDB session get killed uncleanly while
attached, and don't assume a clean-looking detach always leaves the game healthy.** Three times this
session the wine process crashed outright (Wine's own "Program Error"/WineDbg popup, `Exception
c0000005`) - twice after a GDB session ended via `subprocess.run(..., timeout=N)` (which `SIGKILL`s GDB
on timeout) rather than a clean `delete`+`detach`, and once for an undiagnosed reason after a session
that reported a clean detach. A `SIGKILL`ed GDB leaves its software breakpoint's `0xCC` byte physically
patched into the tracee's memory forever (no tracer left alive to restore it) - the NEXT time any
thread executes that address, it traps with no debugger attached and Wine's crash handler fires. Fix
used successfully every time after: a tiny standalone restore script
(`mem.seek(0x4aaba1); mem.write(bytes([0x8d]))` - `0x8d` being this exact build's own original opcode
byte at that address, confirmed by reading `game/D3DPOPTB.EXE` at file offset `0x4aaba1-0x401000+0x400`)
run as a cheap insurance step after EVERY GDB session regardless of how it ended or how clean the
detach looked. Generalizes: any future live session setting a software breakpoint in this exe should
keep a same-recipe restore script on hand and run it unconditionally, and should expect an occasional
hard crash requiring a full level reload even when nothing looks wrong.

## Continued digging on the keyboard/input-reliability question (later session) - a non-interactive GDB automation recipe, a real crash-on-resume, and the mystery narrowed but not closed

Picked up this file's and `docs/trace-backlog.md`'s open "input reliability" thread with two angles:
pure menu-navigation timing experiments (see `docs/trace-backlog.md`'s own write-up of those - net
result: the in-level pause menu's Up/Down turned out to be a CIRCULAR 8-stop cycle, which fully
explains at least some of the "dropped keys" reports as unaccounted wraparound, not real drops), and
redoing this section's own `process_cmd`-breakpoint method headlessly (no interactive terminal) to get
real ground truth on single gameplay hotkeys rather than screenshot-inferred guesses.

**A working non-interactive automation recipe for this method, worked out the hard way**: run
`gdb -q -nx` as root with its stdin attached to a named FIFO (`mkfifo /tmp/gdbin; gdb -q -nx
< /tmp/gdbin > /tmp/gdbout 2>&1 &`), then feed it commands with `cat > /tmp/gdbin <<'EOF' ... EOF`
from separate `docker compose exec` calls. **Critical gotcha**: GDB treats EOF on stdin (which happens
the instant a `cat`/`echo` writer closes, if no other writer is currently connected) as "quit", with any
confirmation prompt auto-answered yes since input isn't a terminal - so a batch of commands that ends
WITHOUT a `continue` (i.e. one that returns to an idle prompt waiting for the next line) will
immediately self-quit the instant that write call's file descriptor closes. **Fix**: always end a batch
with `continue` (or any command that puts the inferior back in a running, non-prompt-waiting state)
before letting the writer close - confirmed this works across several batches (`attach` + `break` +
`commands` block + `continue` all sent as one write processed cleanly, inferior kept running after the
writer closed). A separate, STANDALONE one-line batch like `info breakpoints` with no trailing
`continue` reproduced the EOF-quit immediately, confirming the mechanism. **Reassuring follow-on
finding**: this EOF-triggered quit is NOT the same hazard as this section's own documented
`SIGKILL`-on-timeout warning above - `kill -INT <gdb_pid>` (used to interrupt a running inferior, the
documented way to get back to a prompt) successfully stopped the inferior as intended, and the
breakpoint byte at `0x4aaba1` was confirmed still `0x8d` (the correct original byte, not the `0xCC`
software-breakpoint marker) immediately afterward even though gdb's own process had already exited by
the time the next command was sent - i.e. the EOF-quit that followed the interrupt was a CLEAN quit
(detaches and un-patches breakpoints like a normal `quit` would), not an orphaning one. Only a hard
`SIGKILL` (e.g. from a timeout) skips this cleanup, per the existing warning above - worth keeping
both cases straight for next time, and still worth running the file-offset-byte restore script as cheap
insurance regardless, exactly as already recommended.

**A real, reproducible crash found this session**: with the breakpoint armed and the inferior
`continue`-d, a single mouse click (`xdotool mousemove ... click 1`) cleanly hit the breakpoint -
`HIT ebx=0x66` (already-catalogued `commands.tsv` row: packed cursor-coordinate dispatch, i.e. this
really was the click, not a stray keyboard event accidentally in the same combined `xdotool` call) -
but the very next `continue` crashed the process outright: GDB reported `SIGSEGV` at a corrupted
address (`0xffff800f004aaba1` - note the garbage high bits glued onto the real `0x004aaba1`, looking
exactly like a sign-extension bug in resuming a 32-bit breakpoint under this process's reported
architecture), and Wine's own "Program Error" dialog appeared for `D3DPOPTB.EXE`. This happened on the
FIRST hit of a fresh session, not after many hits or a long run, and every `attach` this session printed
a slightly different architecture-mismatch warning (`i386:x86-64 is not compatible with reported target
architecture i386` one run, `...i386:x64-32` another) - consistent with GDB's own WoW64/target-arch
detection being unstable in this specific Wine build/container combination, and a very plausible
root cause for BOTH the occasional crashes this file already warned about AND at least some of the
previously-reported "a key worked once but then nothing" flakiness: if resuming from a hit has a real
chance of corrupting execution, every session using this method should expect it and treat a sudden
unresponsive game (screenshot stops changing, no further hits) as "probably crashed," check for the
Wine error dialog before assuming input itself is being dropped.

**Still unresolved**: a second, fresh session (clean relaunch, breakpoint re-armed, confirmed set via
`info breakpoints`) produced ZERO hits across several individual `Escape` and one `Return` press while a
tutorial modal dialog ("J'ai créé mon haut lieu de réincarnation...") was up on screen, each checked
individually with the game screenshot confirming it was alive and rendering the whole time (not
crashed, not stuck) - a real non-crash, non-EOF-quit case of keyboard input simply not reaching this
breakpoint, differing from the EARLIER documented session where Escape hit reliably "both inside the
tutorial's own modal OK dialog and in plain gameplay." Not root-caused this session - candidates worth
checking next time: (a) the window-focus hazard this file already documents (many intervening
`docker compose exec`/screenshot calls happened between presses, exactly the pattern previously blamed
for dropped input), (b) modal dialogs specifically may route Escape/Return through a DIFFERENT code
path than `process_cmd`'s main argument-load point entirely (plausible - never confirmed either way),
or (c) a residual effect of the architecture-mismatch warning making this build's breakpoint
unreliable in ways beyond just the resume-crash already found. A concrete next step: re-run the exact
same single-key test immediately after a confirmed-good input moment (e.g. right after the mouse click
that DID hit, in the same session, before any other X11 calls) rather than after a fresh attach with no
prior confirmed-good interaction.

**Resolved immediately after, by elimination**: with GDB fully detached (confirmed via `pgrep`, no
`gdb -q` process left) and nothing else changed, the SAME `Return` keypress that had just failed
silently several times in a row dismissed the still-open tutorial dialog on the very first try. This
points at GDB's mere presence - ptrace-attached to this ~40-thread Wine process, independent of whether
the armed breakpoint ever fires - as the actual cause of that session's input not arriving, rather than
focus loss or a dialog-specific code path (both still-plausible alternatives from the paragraph above,
but this is a cleaner, simpler explanation that fits everything observed: the one click that DID hit
happened right after attaching, before the inferior had been continuously running+ptraced for long, and
every later keypress in that same attached session failed). **Practical takeaway for next time**: treat
any `process_cmd`-breakpoint GDB session as actively degrading input delivery for its ENTIRE duration,
not just something to worry about around the breakpoint hit/resume itself - keep such sessions as short
as possible (attach, get the one data point needed, detach immediately), and don't trust a run of
"no hits" from a long-attached session as evidence about the GAME's own input handling at all; it may
just be evidence that GDB itself is in the way. This also reframes the EARLIER documented
"1-in-4-to-5 hit rate even with good focus" finding from the very first session that used this method -
worth re-measuring that with much shorter attach windows per keypress, now that this confound is known.

## The RC intro's "shaman fires a beam at the stone" visual, traced end to end - and a static mis-read caught by a read-only live poll (later session, 2026-11-08)

Prompted by a user question: "the shaman faces the stone that goes up and there's an animation
between the shaman and the stone, can you trace it?" - the "it rises" half (ground-flatten, 8
staggered pillars, the shaman's own order-kind 18) was already fully documented
(`docs/functions.tsv` `0x433a10`/`0x41c140`/`0x50c690`); the "beam between them" half had never
been chased - the shaman's own state 3 was known to "fire a class-8/type-1 standard shot per
pillar slot," but neither that shot's own per-type init (`init_unit_type_8`'s type-1 case) nor its
per-turn flight handler had ever been opened (the latter was a bare one-line stub: "which exact
behaviour maps to this address is not preserved from the source").

**Resolved the jump table and the two functions statically first**: read `init_unit_type_8`'s own
8-entry table (`0x4bada8`) by pulling its raw dwords directly from the exe file (the same
file-offset trick `docs/trace-backlog.md`'s "Notifications" section already documents for
`process_cmd`'s own tables - `VMA - 0x401000 + 0x400`), confirming type 1 -> `0x4BAB30`. Traced it
and its sibling per-turn flight function (`0x4BAF00`, states 1/2's shared handler) instruction by
instruction - but came away with a mechanically-plausible-looking reading that was actually WRONG in
an important way: a block that copies one field into the object's own current-position field
(`+0x3D`) on its first tick looked, read cold, like it SNAPPED the shot's position straight to its
destination immediately, which would mean no real flight at all (just an instant pop).

**Rather than trust that read, settled it with a cheap, read-only live poll instead of more
disassembly staring** - no breakpoints, no synthetic key presses, so none of this session's earlier
crash risk applied: a short script (scratch-only, not committed) scans the flat thing-id table
(`0x890390`) each tick for any live class-8/type-1 object and dumps its position/destination/launch
fields, run during an ordinary level-1 load (the RC rebuild fires automatically, no player input
needed at all). **The live data overturned the static "snap" reading outright**: across 8 distinct
shot ids (one per pillar ring slot, matching `tribe+0xA0D`'s own 8 slots) sampled turn to turn, each
shot's own `+0x3D` position genuinely moved, turn over turn, from a SHARED launch point toward its
own distinct destination - e.g. one shot's position moved from `(5888,55040,86)` to `(5732,55040,88)`
between two consecutive turns, a real step toward its own destination `(4352,55040,...)`, not an
instant jump. The live data also cleanly resolved which of the two position-like fields
(`+0x70`/`+0x76`) is which - the 8 shots' own `+0x76` values traced out a perfect 8-point ring
(radius ~1536 units) around one shared centre point, which is exactly what all 8 shots' own `+0x70`
held in common - i.e. **`+0x76` is each shot's own individual destination (a ring slot), `+0x70` is
the shared launch point (the shaman's own position/RC anchor)**, the reverse of what a naive
"written first, so it must be the origin" read of the init code suggests.

**The visual itself**: each turn a shot hasn't yet arrived, its flight handler samples up to 20
small jittered points along its own path and spawns a **class-7/type-4 "lightning elem" effect** at
each one - the exact same falling-bolt-chain-link object the Lightning spell's own visible bolt is
built from (`process_lightning_elem`/`0x50BD70`, already documented). So the player-visible effect
really is a beam of sorts: a rapid burst of brief lightning-bolt segments snapping from the shaman
to the target ring slot, resolving (per the live data) within 1-2 turns - matching the
already-documented "staggered 1-3-turn gaps between pillar appearances" from a much earlier session.
Full write-up: `docs/functions.tsv` rows `0x4bab30` (new), `0x4baf00` (rewritten from the old stub),
`0x433a10` (cross-reference added).

**Methodological takeaway**: a static disassembly read that "looks" unambiguous can still be wrong
about which of two similar-looking fields is which, especially for a function explicitly flagged by
an earlier session as having lost its own field semantics; a short, READ-ONLY live poll (no
breakpoints, no synthetic input - just `/proc/pid/mem` reads, the same safe technique
`watch_pillars.py` already established) is cheap insurance worth reaching for whenever a static trace
produces a mechanically-plausible-but-narratively-odd conclusion (here: "the projectile instantly
teleports to its target," which would be a strange thing for this engine to actually do given the
many OTHER shot types that visibly fly).

## Reproducible mouse-click recipe for loading a specific save, and the real root cause of the cursor-drift bug (later session, 2026-11-11)

**Root cause, refined across the session (an earlier draft of this section blamed a
DirectInput-exclusive MOUSE - wrong)**: `WINEDEBUG=+dinput` shows the exe acquiring two DirectInput
devices (`DISCL_FOREGROUND|DISCL_NONEXCLUSIVE` and `DISCL_EXCLUSIVE|DISCL_FOREGROUND`), but
**neither is the mouse** - a prior session already identified the second device (`0xd05e58`) as the
joystick, and the mouse is handled through ordinary win32 events. The key fact: **the game keeps
its OWN internal cursor position (an accumulator fed by mouse events), and its menu hit-testing,
hover highlighting and cursor sprite all follow that internal position, not the live X11 pointer.**
A large pointer warp (one big `xdotool mousemove`, or a fresh VNC connection's first pointer event)
desyncs this accumulator from the real pointer; small continuous deltas (real mouse motion, small
`mousemove_relative` steps) track fine. Confirmed from a `WINEDEBUG=+cursor,+win,+message` capture:
a click was delivered as `WM_LBUTTONDOWN` at the exact intended window-local coordinate
(`X11DRV_ButtonPress ... pos (320,220)`) **and the menu still did not react**, because the game
hit-tested against its own (shifted) internal cursor, not the message coordinate. The
`MouseWarpOverride=disable` / `Managed=N` registry keys under `HKCU\Software\Wine\X11 Driver` did
NOT fix this (reverted; not part of the recipe).

**The internal cursor position was found by live memory scan (scan for (x,y) dword pairs, nudge the
pointer by a known delta via small relative steps, keep pairs that moved exactly that delta) - five
dword-pair globals, all holding the same window-local (x,y), plus two related neighbours:**

| Address | Holds |
|---|---|
| `0xD0597C` | internal cursor (x,y) - in the same region as the DirectInput device structs (`0xd05e58` joystick), likely the primary accumulator |
| `0xA69030`, `0xA69070` | same value - game-side copies (`0xA69078`, right after, is the offset pair `0x4AA1C0` subtracts in its 0x200/0x180 mode) |
| `0x749C90`, `0x749DF4` | same value - further copies |
| `0xA69038` | cursor + a small constant offset (~26,27) - hotspot or previous-position |
| (heap, e.g. `0x364fe7c`) | wine's X11-side position - tracks the REAL pointer, useful as ground truth |

**The instant fix (no game restart needed): write the real pointer's window-local position into
those five dwords** - `scripts/cursor_resync.py` (committed) does exactly that, run inside the
container as root with the mouse held still:

```
docker compose exec -u root pop3 python3 /repo/scripts/cursor_resync.py
```

Live-confirmed: the rendered cursor snaps to the real pointer immediately (hover highlight updates
too) and STAYS in sync through subsequent small-step movement. Re-run it whenever drift reappears
(after any big warp - including right after connecting over VNC: connect, put the mouse inside the
game window, hold still, resync, then move normally).

**If writing memory is not an option, the workaround is: never send one large absolute `xdotool
mousemove`; move in small `xdotool mousemove_relative -- dx dy` steps (≈±10 to ±40 px per step,
short `sleep` between steps).** This tracked 1:1 across an entire menu→load-list→row-select→load
sequence. A single large relative jump also desyncs - break big moves into several small steps.
Watch the window edges: the real pointer can exit the 640x480 window while the rendered cursor
appears stuck inside (motion stops being delivered once the pointer leaves the window rect), and
cursor-at-edge also triggers in-game camera scrolling.

**Reproducible click/step recipe to load a specific save from the main menu**, captured this
session at window position `728,455`, size `640x480` (confirmed via `xdotool getwindowgeometry`;
re-check if the window ever opens at a different position/resolution). The main menu's highlighted
item persists across restarts (see "Docker headless rig" above) so the exact first move needed
varies; the shape of the recipe is: small relative steps toward the target, screenshot to confirm
the right item is highlighted, click (explicit `mousedown 1`/sleep ~0.15s/`mouseup 1`, not plain
`xdotool click 1` - that was observed to silently no-op at least once this session), screenshot to
confirm the click landed, repeat for the next target:

| Step | Target | Approx. local offset (x,y) from window top-left |
|---|---|---|
| 1 | Main menu "CHARGER PARTIE" | `(320, 220)` |
| 2 | Load-list row 1 (default-highlighted save) | `(90, 174)` |
| 3 | Load-list row spacing | `+18` per row down (row *N* ≈ `(90, 174 + 18*(N-1))`) |
| 3b | 2nd-last row in this save list (row 7 of 8) | `(90, 290)` |
| 4 | "CHARGER" button (under the list) | `(320, 410)` |

Selecting a specific list row sometimes still lands one row off on the first click (the list box's
clickable text also starts a little right of its left border - click inside the text, e.g. local
x≈90, not right at the border edge x≈60, which visually hovers but doesn't select) - nudge with one
more small relative step (`±18` in y) and re-click if the highlighted row isn't the intended one
yet. This off-by-one-row hiccup persisted even with the small-step technique and is a separate,
minor issue from the large-jump desync above.

## RC shot trail corrected: it's a small sparkle, NOT a lightning bolt (later session, 2026-11-08)

The previous session's own "it's a chain of lightning-bolt segments" conclusion was wrong - caught by
the user, who had already implemented it in open-populous and compared it against the real game.
Re-traced statically first, then confirmed with actual screenshots.

**Static re-read found a real error in the earlier trace**: `0x50BEB0` (called from `process_lightning_elem`/
`0x50BD70` once a falling piece's own lifetime expires) does NOT spawn a new chained object - it was
misread. It operates on the SAME `self`: sets its state back to 4 (falling) and calls `unit_set_object`/
`0x4EE700(&self+0x33, kind, offset)`, where `offset` is the object's own CURRENT sprite index plus 4 and
`kind` (1, or 0x1D once a threshold byte is hit) selects a row in the draw-class table `0x5A6AF8`. So this
is one single object that falls under physics and periodically advances its own sprite frame/draw-class -
not a chain of multiple pieces each spawning the next. Table row 1 (the normal case) is a near-empty,
minimal entry - nothing in it suggests a dramatic zigzag bolt shape.

**Live screenshots settled it beyond doubt.** Set up the same Docker rig, loaded level 1, and this time
captured the exact turn window (37-52) tightly - a small script polling `simulation_turn` directly and
firing `import` screenshots only while turn was in range, avoiding the earlier sessions' problem of
screenshots landing well before or after the shot-firing window. Zoomed crops of turns 37 and 41 show
the effect clearly: a single tiny, tribe-coloured (blue, matching the local tribe) 4-point sparkle/glint,
floating near the shot's current position - visually indistinguishable in style from the small gold
sparkles the ground-levelling ring effect already uses nearby, just a different tint. **No bolt, no
zigzag, no jagged line, nothing connecting the shaman and the stone at all** - the "connection" a player
perceives is just "a few twinkles drift from near her to near the slot, then the stone appears," not a
rendered beam of any kind.

**Corrected**: `docs/functions.tsv` rows `0x50bd70` (now named `process_lightning_elem`, rewritten to
describe the real single-object sprite-advance mechanism), `0x4baf00` (the "lightning elem"/"crackling
arc" language replaced with "falling spark"/"tiny sparkle"), and `docs/unit_types`'s own class-7/type-4
row (renamed from "lightning elem" to "falling spark" with a note on the correction). The object is still
genuinely SHARED with Lightning's own falling-bolt-chain (confirmed, same function), but its actual
on-screen appearance is a generic small sparkle, not anything lightning-shaped - the old name was an
unverified guess (almost certainly inherited from "this is the same object Lightning's code uses" without
ever checking what it draws), not a finding, and no future session should assume a "lightning" label in
this catalog means the game actually draws a bolt.

**Methodological note, sharpening the previous session's own one**: a live screenshot beats both a static
disassembly read AND a live memory-poll of struct fields when the question is specifically "what does
this look like" - the earlier position-tracking poll correctly proved the object moves, but said nothing
about its shape/colour, which is exactly the kind of claim this session's static trace got wrong by
inferring it from a type NAME in `docs/unit_types` (itself unverified) rather than the actual sprite/
draw-class data. Tight-window screenshot timing (poll `simulation_turn` in-process, fire `import` only
while in the target range) is the fix for the earlier sessions' own "screenshots landed outside the
window" problem - worth reusing for any future "what does X actually look like" question.

## Spy disguise player path, cracked end to end live - and the breakpoint methodology that finally worked (session 2026-11-11)

**The question** (open across many sessions): what actually happens when the player, with a spy
selected, clicks the per-tribe HUD square (the red/yellow/green stack above the spy's population
icon, one square per other tribe - its own hover/click tooltip is "Icône tribale <name> : voir
l'encyclopédie...") to order a disguise. Static analysis had the application primitive
(`0x4DE760`) and a suspected order kind (16) but never the player-facing trigger.

**The answer, live-confirmed** (the user drove the game over VNC; all three captures agree):

1. HUD tribe-square click (spy selected) arms a per-tribe action byte (`0x89da88` table, values
   5-7 observed) + pending flag `0x895e9b`, and lands as **`ui_cmd 0x7e`** in `process_cmd`.
2. `ui_cmd 0x7e` calls **`0x4AA8B0`**, which queues
   `set_tribe_command(player_tribe, (0x37|0x57)+idx, cached_click_pos)` ->
   **`tribe_cmd 0x5c/0x5d/0x5e`** (flagged variants of bases 0x3c-0x3e).
3. `process_tribe_cmd`'s shared case (`0x43EDEA`) -> second-level dispatcher **`0x444F60`**
   (opcodes 0x1E-0x5E) -> stages `tribe+0x8C1` (`0x435780`) -> `0x435C40`+**`0x435CB0`** builds
   ONE command group (**order kind 0x10**, target tribe in `group+0x6`) and assigns it to every
   selected unit's **secondary** order slot `+0x8B[0]` via `group_assign 0x436d00` (slot write
   live-captured at `0x436d4e`; ordering 4 spies at once produced one shared group id in all four).
4. Next sim turn: `order_execute` kind-16 inline case (`0x43281b`) calls
   **`0x4DE760(spy, tribe)`** -> `+0xB2 = tribe<<6 | 63` and the familiar countdown. Captured
   mid-write at `0x4de799` (`+0xB2` read back `0x3F` with the game frozen between the two write
   steps, `0xFF` after resume, `0xC0` once the countdown elapsed).

Catalog rows: `commands.tsv` `tribe_cmd 0x5c/0x5d/0x5e`, `ui_cmd 0x7e/0x7f`; `functions.tsv`
`0x4aa8b0`, `0x444f60`, `0x435780`, `0x435cb0`, plus updated `0x4de760`/`0x432d18`. Open ends in
`trace-backlog.md`: the ARM half (the square click's own handler - `0x895e9b` setters cluster
around `0x438100`-`0x4382xx`), the exact idx->kind-0x10 mapping, the 0x37-vs-0x57 base variant
meaning, which of 0x5c/0x5d/0x5e maps to which tribe/action, and `ui_cmd 0x7f`'s own role.

**Methodology - what finally made live capture reliable (and what didn't):**

- **The resume-after-hit crash is NOT avoided by `hbreak` or by `set architecture i386`** - a
  hardware breakpoint at `0x4de760` with an auto-`continue` commands block still SIGSEGV'd the
  game on the first resume, exactly like the software-breakpoint sessions. BUT the hit's own
  `printf` lands in the log BEFORE the crash, so "arm, let it hit once, read the log, restart the
  game" yields one clean data point per run even when every resume dies. Two of this session's
  captures were exactly that.
- **The pattern that avoids the crash entirely: a hardware WATCHPOINT with NO `continue` in its
  commands block.** The game freezes at the faulting write; read everything calmly (`info
  registers`, `x/80xw $esp` - raw return addresses in the 0x4xxxxx range give the full call chain,
  since `bt` stays broken under the architecture mismatch); resume manually only when ready, or
  `delete` + `detach` without ever resuming past a trap. No crash occurred in any of this
  session's watchpoint stops, across several fire/resume cycles.
- **Watch the data, not the code**: watching the spy's own `+0xB2` (disguise byte) and `+0x8B`
  (secondary order slot) caught both halves of the mechanism with zero noise, where breakpoints on
  shared code (`0x4de760`, `process_cmd`) caught mostly background/AI hits. A first watchpoint on
  `+0x9B` (primary slot) that NEVER fired while the disguise still applied is itself what proved
  player orders land in the secondary slots.
- **Expect one false fire per order lifetime**: the order's own completion CLEARS the watched slot
  (write at `0x43668a`, from `order_execute`'s shared tail) - resume past it before the real test.
- **FIFO-gdb improvements over the documented recipe**: keep a persistent dummy writer
  (`exec sleep 100000 > /tmp/gdbin &`) holding the FIFO open, so each command batch's writer
  closing no longer EOF-quits gdb - this made multi-phase sessions (re-arm, resume, re-read)
  practical. `kill -INT <gdb pid>` remains the way to get a prompt while the inferior runs.
- **`winedbg --auto` from a prior crash dialog holds ptrace on the game** and blocks `/proc/mem`
  writes (EIO) until killed. Separately, even with NO tracer attached, direct `/proc/<pid>/mem`
  WRITES returned EIO on a page that mapped `rwxp` and read fine (cause not identified - reads
  never failed); `gdb -batch -p <pid> -ex 'set {int}ADDR = VAL' -ex detach` is the reliable
  fallback writer, used for cursor resyncs while investigating.
- The cursor-desync fix (own section above) held up as the enabler for the user's VNC driving:
  resync after connecting, and after any big warp.

### Follow-up, 2026-11-12 (static): the ARM half and every remaining detail of the disguise chain

All five open leads from the session above are now resolved or sharply narrowed, statically (no live
session needed - the capture data was enough to anchor the reads):

- **The opcode trio 0x5c/0x5d/0x5e does NOT encode the action or the tribe** (corrects the first
  write-up): the commit opcode is `base + slot` where slot = the tribe's pending-order staging-ring
  cursor (`tribe+0x8C0`, count `tribe+0x8BF`, records `tribe+0x8C1`+slot*10, advance fn `0x4358F0`).
  The ORDER KIND (0x10) and the target tribe id travel in the tribe_cmd's own argument fields.
- **The ARM half**: hovering a HUD tribe square runs widget callback `0x49D5F0` - square ordinal
  (`widget+0x63`) -> the Nth NON-player tribe id (own tribe skipped) -> global `0x5cae80` (0xFF =
  none). Per frame, `0x437010` rebuilds the cursor-context bitmask `0x895e7a` (`0x5cae80 != 0xFF`
  -> bit 0x2000) and `tribe+0xC23` = bitmask of SELECTED person types (`1 << type(+0x2B)` for every
  person with selected-flag `+0x7A` bit 0x80). `0x437750` then picks the armed action: candidate
  kind 0x10 (disguise) requires context bit 0x2000 AND a selected type matching the kind's
  compat mask (`0x5a7dc4 + kind*22`) - **kind 0x10's mask is 0x20 = 1<<5: spy (type 5) only**.
  `0x4380F0` validates it against the context each frame into `0x895e9b` ("a click would act").
- **ui_cmd 0x7e vs 0x7f**: a variant pair (0x7e -> opcode base 0x57, 0x7f -> 0x37), driven by
  input-modifier state bits (`0x98e908/9`); the 0x57 family suppresses staged-flags bit 0x80
  downstream - plausibly queue-vs-replace. Which real button/modifier maps to which: unconfirmed.
- **Pitfall worth remembering**: reading .data-section constants from the exe with the .text
  formula (`VMA - 0x401000 + 0x400`) silently returns wrong bytes - kind 0x10's compat mask first
  read as 0x100 (nonsense) instead of 0x20 (spy). Use the PE section table to map VMAs to file
  offsets for anything outside .text.

Full rows: functions.tsv `0x437010`/`0x437750`/`0x4380f0`/`0x4358f0`/`0x49d5f0` (new),
`0x4aa8b0`/`0x444f60`/`0x435780`/`0x435cb0` (corrected/extended); commands.tsv `tribe_cmd
0x5c-0x5e`, `ui_cmd 0x7e/0x7f` (rewritten). Still open: which input maps to 0x7e vs 0x7f, the
per-code jump table inside `0x4380F0` (armed codes 1-0x22), and the player arson path (unchanged).

## Spy arson, live (2026-11-12): injecting an order the player cannot give, and what the fire really does

**Question** (user): how exactly does a spy set a building on fire - where it stands, the match, the
effect, the duration, the damage, and whether it gets revealed. Arson (order kind 15) is provably not
player-armable (see the disguise sections above), so the live trace had to **inject the order into
memory**: `scripts/inject_order.py` (committed). `auto X Z TRIBE SECONDS` mode finds the nearest live
building of TRIBE to (X,Z) and the nearest live tribe-0 spy (wrap-aware distances - the map wraps at
65536), asserts both records are what they should be, disguises the spy as TRIBE (settled), writes a
kind-15 group and assigns it, then logs every turn: the spy's state/substate/disguise, a byte-level diff
of the building record, and every new class-5/7/8 object within 3000 units.

**Order injection recipe** (what made it work after two failed tries):
- group record (`0x938830 + id*10`): `+0` kind, `+1` flags, **`+2` reference count (u16) - set it to 1
  and increment the live-group counter `0x96AA7A`**; a refcount of 0 underflows when the order is
  released (the most likely cause of the first attempt's crash). `+6/+8` = target, encoded per the kind's
  record (kind 15: a cell-centered position, `(x & 0xFE00) | 0x100`).
- unit: `+0x9B` = group id, `+0x2C` = 10 (carrying out an order), `+0x2D` = 0, **and set `+0xC` bit
  `0x40000000` (the "order (re)starting" flag the handlers test on entry) - without it the unit sits in
  state 10 forever**, doing nothing.
- re-validate the target unit right before writing: in an active war, spies die and their slots get
  reused within minutes (one attempt wrote onto a tribe-3 preacher that had taken a dead spy's slot -
  reverted). The script now asserts class/type/tribe first.
- pick a target the spy can reach without crossing a third tribe: a first run disguised as tribe 2
  walked the long way round through tribe 3's village, got attacked (disguise dropped to the real tribe
  the moment the fight began) and died.

**Results** (all now in `functions.tsv` `0x439d30`/`0x408ab0`/`0x498140`/`0x40a6b0`, `effect_states.csv`
29, `sound.tsv` 0x36/0x53, and pop3-rev-analysis.md "Spy disguise and infiltration"/"Burning building"):
spy stands on a flagged wall cell of the footprint (~830 units from the hut's center), aims 10 turns,
winds up 24 turns holding the firebrand prop, throws (sound 0x36, a cosmetic ember with a 64-turn life),
8 turns later the order ignites the hut (attacker = the spy's REAL tribe), 24-turn withdrawal. The hut:
4 flame objects, occupants out at T+7, smoke and embers, ONE -100 wood hit at T+47 (a stock companion is
created at full cost first: big hut 300 -> 200, build stage 4 -> 2), burn ends T+126 in "needs wood"
state - damaged, not destroyed. The spy kept its disguise through the whole order; it was revealed ~160
turns later while idling at the scene.

**Correction made the same day**: both class-7 dispatch tables (`0x50A59C` init by type, `0x50AFD4` per
turn by state) are indexed **value-1**. Reading them as value-indexed made the firebrand look like it
shared lightning's strike-point state - the live object's state 29 is what exposed the off-by-one.

### Follow-up: what actually un-disguised the spy (watchpoint capture, same day)

The first arson run's spy lost its disguise ~160 turns after the fire while idle, unhurt and with no
order, which left two candidates open. A second run (save reloaded, same disguise, same target) with a
freezing hardware watchpoint on the spy's `+0xB2` caught the reveal in the act: the call chain on the
frozen stack was `main_loop_outer -> process_tribe_1 -> process_tribe_2 -> maybe_ai_func_1 (tribe 3's AI
goal tick) -> 0x4C5CF0 (AI task branch dispatcher) -> 0x4F8E10 (spy discovery roll) -> 0x4F35B0 (area
reveal sweep) -> 0x4DE7F0 (reveal)`, with tribe 3's record as the argument. **It is the imitated tribe's
computer AI running a discovery check - not combat, not an enemy spy, not an order.** This time it struck
mid-windup: the unmasked spy was attacked, knocked back to the start of its order, retried twice and was
killed, and the hut never caught fire. The roll is random and can fire any time the spy is in that
tribe's area (here before ignition, in run 1 ~13 s after it).
Reusable pattern: `watch *(unsigned char*)(spy+0xB2)` with a commands block that prints `$pc` and
`x/96xw $esp` but does NOT `continue` - the game freezes at the write, read the return addresses, then
`delete`/`detach`. No crash across all of today's watchpoint stops.

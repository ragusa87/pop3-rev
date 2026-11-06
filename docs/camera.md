# Camera and flyby investigation

Working notes for the original game's live camera (`D3DPOPTB.EXE`), built to calibrate
`open-populous`'s `flyby.rs` zoom/angle guesses against level 1's opening flyby script
(`open-populous` `docs/specs/ai-scripts.md` "Worked example: level 1's opening flyby"). Clean-room
findings (pseudocode/formulas, no literal decompiled code) go to `open-populous`
`docs/specs/pop3-rev-analysis.md` "Camera flyby state (tribe_struct)" and `TODO.md`; this file is
the fuller working log behind that - raw addresses, candidate fields, confidence levels, dead ends,
and the tools used, kept here because `pop3-rev-analysis.md` is the addressable reference for
`open-populous` and shouldn't carry every intermediate step.

## Tool
`scripts/watch_camera.py` (uses `livemem.py`'s `find_game()`, works against either binary). Must be
run by the user themselves (`sudo`, needs a real terminal for the fingerprint/password prompt - a
background retry loop just spams fingerprint-reader prompts, don't do that again).

```
sudo python3 scripts/watch_camera.py [--every SECONDS]            # fixed field list (matrix, K/D/S, dead-end candidates)
sudo python3 scripts/watch_camera.py --scan-tribe [--every SECONDS]  # dumps tribe_struct +0x00..+0x880, prints only changed dwords, tagged with the game turn
```

`scripts/watch_addr.py` (new, a later session): a live GDB hardware write-watchpoint on one address
(literal, or `tribe+0xOFFSET` for a tribe_struct field) - use when static disassembly can't find a
single recognizable immediate for an address because it's only ever reached through a computed base
register (see "`tribe_struct+0x2c` solved" below, its first use). Needs `gdb` in the Docker image
(`docker/Dockerfile`, added this session - rebuild with `docker compose build` if your image predates
this) and real ptrace, so run it via `scripts/docker/watch_addr.sh tribe+0x2c [--seconds N]` inside the
headless rig (root inside the container, no host sudo prompt) rather than directly on the host.

## Confirmed

### The rotation matrix lives in tribe_struct, not a separate camera struct
`clear_land_draw_state` (0x46E700/0x46E168) copies 36 bytes (9 dwords) every frame from a pointer at
`0x74A350` into the fixed `0x74A354..0x74A374` buffer the projection code reads. That pointer is
rebuilt each frame (`update_vfconfig`/0x417338, write site 0x41741C) as
`0x89D1C8 + tribe*0xC65` - the already-documented tribe record base/stride (`docs/cheat.md`) - for
the LOCAL PLAYER's own tribe (index byte at `0x89C6F0`). So the matrix is the active player's own
tribe_struct's first 36 bytes (offset `+0x00`), not a global camera struct - fits a hot-seat design
where each tribe remembers its own last camera orientation.

### Matrix decode
Column order `M00 M01 M02 / M10 M11 M12 / M20 M21 M22`, slots at `+0x00, +0x04, ... +0x20`:

```
M00=cosY  M01=0        M02=sinY
M10=sinP·sinY  M11=cosP  M12=-sinP·cosY
M20=-cosP·sinY  M21=sinP  M22=cosP·cosY

yaw   = atan2(M02, M00)      # M02 at +0x08, NOT +0x0C - a transcription slip briefly produced garbage
                              # yaw, caught by cross-checking against the known 315° idle hold
pitch = asin(M21 / 16384)     # M21 at +0x1C
```
Internally self-consistent (every slot cross-checks against the others to rounding). Resolves
`pop3-rev-analysis.md`'s former "yaw not decoded" note.

### Pitch is not a fixed per-game constant
Earlier sessions only ever sampled idle holds, both of which read the same pitch (`cosP=15357/16384`,
`sinP=-5709/16384`, ≈-20.4°, matching `open-populous`'s own `GROUND_PITCH_DEG`) - that's the idle/
resting pitch only. A full capture of level 1's opening flyby (`cam5.txt`) shows pitch swinging
dynamically from that idle -20.4° down to about **-55.4°** around turn 130-140, back up, then
holding flat again for a long stretch (turns 185-270, ≈7s) while **yaw keeps sweeping continuously
underneath it** (171.6°→237.3°→228.3° over that same window) - yaw and pitch are driven
independently during a flyby, not locked together. `open-populous`'s `flyby.rs` currently never
touches `CameraRig.pitch` during a flyby (only `focus.x/y`, `yaw`, `distance`) - confirmed gap.

A later, independent full-flyby capture (`cam7.txt`, turn-continuous from 81 to 438, see "Raw
capture logs") reproduces this exactly and pins the low hold precisely: pitch bottoms out at
**-55.37°/-55.38°** (`M21=-13481..-13483`) and holds flat for a 31-32 turn plateau, **turns
134-165** - tighter than the earlier "around turn 130-140" estimate, same value.

### `FLYBY_START`'s turn - SOLVED EXACTLY: turn 72
Open question #1 is closed. Ran the existing `cargo run -p pop3-ai-script --example ai_script_info --
<path to cpscr010.dat>` dumper (the user's own hint: "use the command to dump level info" - level 1's `.hdr`
byte 89 gives AI script number 10 for the red tribe, i.e. `cpscr010.dat`) against the real script file and
read the parsed AST directly instead of curve-fitting captured motion. The flyby's own gating, read straight
from the compiled script:

```text
Every { period: 8 }:                           # checked only on turns where turn % 8 == 0
  If INT_GAME_TURN > 70:
    If $57 == 0:
      DO CREATE_MSG_INFORMATION(78)             # the reincarnation-centre intro message
      DO SET_MSG_AUTO_OPEN_DLG
      DO SET_MSG_DELETE_ON_OK
      DO ENABLE_USER_INPUTS
      $57 = 1
      <the whole FLYBY_CREATE_NEW..FLYBY_START sequence, folded into one AST node>
```

The first turn where `turn % 8 == 0 AND turn > 70` is **turn 72** - exact, not an estimate, straight from the
script's own logic (no live memory needed at all). This also nails down the mechanism: the flyby starts in
the exact same script tick that pops up the intro message and calls `ENABLE_USER_INPUTS`, confirming "the
reincarnation centre's intro plays turns 0-70, flyby starts right after" down to the turn.

Old approach (curve-fitting camera motion against assumed keyframe timing, superseded by the above): the
first `ANGLE` keyframe predicted a plateau at `FLYBY_START+40`, observed yaw plateau ≈119-120 gave
`FLYBY_START ≈ 80-ish`; the `POS`/`ZOOM` channels' own hold windows landed in the same rough range once
fitted (see "Joint fit" below, now superseded for pinning the start turn, though the fit quality discussion
there still stands for the channels' own scale/offset).

### The intro message dialog pauses the global turn counter, not just script logic
`turn` (`0x89D188`) itself - not just the AI script's own execution - stops incrementing while the
turn-72 `CREATE_MSG_INFORMATION(78)` dialog (see above) is on screen: a fresh capture (`cam6.txt`)
sat dead flat at `turn=76` (the first `turn%8==0` tick after 72 where the poll happened to land)
for several real seconds, matrix/`K`/`cam_x`/`cam_z` all frozen too, then resumed incrementing
immediately on the same poll where the player dismissed the dialog (Enter/OK) - no missed turns,
no catch-up jump, it simply continues from 76. So `FLYBY_START`=72 (previous session, exact, from
the script AST) is the script's own logical turn, but the flyby's real/wall-clock on-screen start
additionally waits on however long the player takes to dismiss this one dialog - relevant if
`flyby.rs` or any host-side timing ever needs to match wall-clock rather than turn count.

Captured end-to-end with the level running fully headless (Xvfb + Wine virtual-desktop window,
no real X server/GPU, `scripts/docker/*.sh`, see that tooling's own notes) instead of a live manual
play session - first time this investigation's tool (`watch_camera.py`) has been run against a
process neither started nor watched interactively by a human the whole way through. Confirms the
game's own turn pacing (~12/s) is unaffected by that environment (turn deltas between poll
timestamps stayed consistent with 12/s throughout, both before and after the dialog pause).

The flyby's matrix had visibly settled to a new, different steady orientation by the time it
finished (`m0=-4996 m2=15604 m3=-5438 m4=15357 m5=-1741 m6=-14626 m7=-5709 m8=-4682`), vs. the
idle-hold values it started from (`m0=11585 m2=-11586 m3=4036 m4=15357 m5=4036 m6=10859 m7=-5709
m8=10859`, yaw `atan2(-11586,11585)≈-45°≈315°` - matches the already-documented 315° idle hold
exactly, a good sanity check that this capture's addresses/decode are still correct). Decoding the
final matrix's yaw (`atan2(15604,-4996)≈107.8°`) against the script's own last `ANGLE` keyframe
value (`1438`, from the `FLYBY_SET_END_TARGET` recap above, `1438/2048*360≈252.8°`) lands almost
exactly 180° apart (`252.8-180=72.8°` vs. the matrix's `107.8°`'s own reference angle `72.2°`) -
a single data point, not proof, but a concrete lead for open question 5's D3D-axis caveat: worth
checking properly against `cam5.txt`'s per-turn `ANGLE`-vs-decoded-yaw data (which has far more
resolution than this one before/after pair) rather than re-deriving from scratch.

### `FLYBY_SET_EVENT_POS`/`_ZOOM`/`_ANGLE` argument order
Confirmed `(value, start, duration)` for `ANGLE`/`ZOOM`, `(x, z, start, duration)` for `POS`, by
cross-checking against `FLYBY_SET_END_TARGET 20 216 1438 0`, which exactly restates the LAST
waypoint's x/z (20,216), the LAST angle keyframe's value (1438), and the LAST zoom keyframe's value
(0) - i.e. it's a plain recap of each channel's final value, pinning the argument positions.

## Candidates, NOT confirmed

tribe_struct fields right after the matrix (`+0x24` on; the struct's own known fields resume at
`+0x881`, `docs/cheat.md`'s list, "person_units"), found via `--scan-tribe` during the flyby
(`cam4.txt`, `cam5.txt`):

| Offset | Observed shape | Candidate | Confidence |
|---|---|---|---|
| `+0x24` | packed dword, two 16-bit halves move independently | camera focus x (low half), z (high half) | **CONFIRMED** (see "POS and ANGLE channels" below): directly written by the `POS` channel's tick callback (`0x449760`), world units = `(cell+1)*256`; scale/offset now solved too |
| `+0x28` hi 16 bits | wraps like a cyclic angle; flat exactly when pitch is flat even while yaw keeps moving (decisive: turns 185-270, yaw moves freely, this field and pitch both sit dead flat for 85 straight turns) | raw pitch angle | **RULED OUT as any memoryless function of current pitch** (see "`+0x28` is not a function of current pitch" below) - correlates in shape, not in value |
| `+0x28` lo 16 bits | pinned at constant `0x0065` the whole capture | unrelated adjacent byte/flag | - |
| `+0x2c` | smoothly monotonic, always an exact multiple of `0x10000` in both captures | N/A - **not a real field, see below** | **SOLVED this session, open question 6 CLOSED**: it's a scan artifact, not an independent value - see "`tribe_struct+0x2c` solved" below |
| `+0x30` | ramps between 0 and exactly `0x1000000` (2²⁴), direction flips at each transition, holds at the max through idle/hold windows | per-segment interpolation progress, 8.24 fixed point (0.0-1.0) | plausible shape, not cross-checked against a ground-truth progress value |
| `+0x34` | **CONFIRMED** (see "The real AI-script zoom chain" below): the zoom channel's own live, signed Q14 fixed-point accumulator (16384 = 1.0, same scale as the rotation matrix), clamped to [-16384, +16384], written every turn by `0x449B30`'s tick callback and fed straight into `0x41C700` to blend camera-preset render-block fields. The "grows with an almost-constant second difference" shape this table used to describe is consistent with `0x44A070`'s own (not fully traced) per-tick increment scheme. |

**Ruled out** (checked, don't revisit without new evidence): `cam_x`/`cam_z` (`0x89CE49`/`0x89CE45`),
the zoom slider pair (`0x89CE3F`/`0x89CE40`), and the projection's `D`/`S` (`0x87CA64`/`0x87CA68`)
never changed across three captures, including one with real arrow-key pans and zoom-wheel input.
These are `process_cmd`'s debug pan/zoom key handlers (`switchD_004AABCA` caseD_32-3D), not live
camera fields in actual play - a dead/unused code path (same genre as the `ui_cmd 0x6D` mistake in
`docs/commands.tsv`). `K` (bend, `0x87CA5C`) DOES vary live, oscillating during camera transitions,
matching the documented "render block can blend" behaviour.

## `+0x28` is not a function of current pitch (open question #2, strengthened dead end)
`cam7.txt` (see "Raw capture logs") is the first capture where the rotation matrix (`+0x00..+0x20`,
including `M21` at `+0x1C`) and `+0x28` were recorded in the SAME `--scan-tribe` run, so the two can
be regressed against each other directly instead of eyeballing two separate captures.

- **Best-case linear fit, `+0x28` hi 16 bits (signed) vs. `M21`: R²=0.395** - clearly correlated in
  direction, far from a clean function. Trying every lag from -30 to +30 turns (in case `+0x28` is
  an eased/delayed copy of pitch, the same way `+0x34` eases toward the `ZOOM` channel's target
  instead of tracking it instantaneously) never exceeds **R²=0.392** (best at lag 0..-3) - a lag
  does not rescue the fit, so this isn't simply "the right relationship with a delay."
- **Decisive counter-example, same capture**: at turn 90 `M21=-5709` (idle pitch, -20.4°) pairs with
  `hi28=-24753`; at turn ~250 (mid-flyby hold) `M21=-5473` (-19.5°, a *more* idle-like pitch, closer
  to level) pairs with `hi28=-21012` - a 3700-unit swing in `+0x28` for a *smaller* pitch difference
  than the first pair, in the wrong direction for any single-valued function (monotonic or not) of
  `M21` alone.
- **Conclusion**: `+0x28`'s hi 16 bits track pitch's general shape (rises/falls together, flat
  exactly when pitch is flat - true in every capture so far) but are not determined by the current
  (or recently-lagged) pitch value by themselves. Likely explanations, not yet distinguished: (a) a
  genuinely different quantity from a different subsystem that happens to move in sympathy with
  pitch during a flyby (the same "shared offset, different class's usage" risk this file's own
  caveats already flag elsewhere), or (b) a stateful/path-dependent value (hysteresis, an
  accumulator with its own history) rather than a pure function of one input. Don't re-attempt a
  plain scale/offset/lag fit against `M21` without first finding a reason to expect (b) resolved -
  the two data points above already rule out every version of (a): a simple function of pitch.

## Joint least-squares fit (`cam5.txt` against the script's 15 keyframes)
Grid search on candidate `FLYBY_START` turn, closed-form affine regression per channel (scale/offset
unknown a priori), both linear and smoothstep easing tried. Scratch script, not kept in the repo.

- Confirms `+0x24`'s LOW half ≈ x, HIGH half ≈ z, not reversed: at every candidate turn, the
  unswapped assignment scores far better than swapped (e.g. at turn=100: unswapped R²=0.40/0.10 vs
  swapped R²=0.02/0.04).
- Linear interpolation edges out smoothstep slightly at every candidate turn tested (e.g. turn=100:
  zoom R²=0.585 linear vs 0.577 smoothstep) - weak evidence, not decisive.
- The channels do NOT share one sharp joint optimum: the zoom channel's own fit peaks around
  turn≈93-95 (R²≈0.59), the position channel's keeps improving out to turn≈106-108 (R²≈0.52) - about
  13 turns apart. R² in the 0.1-0.6 range reads as "clearly the right general shape," not "formula
  nailed." Possible causes: `duration` may not mean a simple lerp/smoothstep window exactly as
  assumed; the channel-argument-order assumption could still be subtly off for one command; or
  `FLYBY_START` genuinely isn't one shared constant if different channels' timers start from
  slightly different internal events.
- `ai-scripts.md` "Flybys" notes `FLYBY_SET_EVENT_ANGLE` goes "the shortest way" - one measurement
  this investigation made saw yaw take what looked like the long way round (0°→188.4°). Since yaw is
  a confound of this `ANGLE` channel AND the `POS` channel's own continuous re-aiming (not yet
  separated), that observation is not a solid refutation of "shortest way" - just unresolved.

## Zoom channel (`+0x2c`) trajectory reproduced - ruled out as a simple linear decode of the raw zoom value
Re-parsed `cam4.txt` and `cam5.txt` (both `--scan-tribe`, independent captures) for `tribe_base+0x2c`'s own
value over time. Result is **clean and reproducible across both captures** - same shape, same key values,
in both:

- **Idle/default value: exactly `1932 × 0x10000`** (`0x78c0000` = 126 615 552) - the field only ever moves in
  whole multiples of `0x10000`, confirming the earlier "always an exact multiple of 0x10000" note; it holds
  here before the flyby starts and returns to it at the very end.
- During the flyby it swings down to a reproducible **minimum of `1733 × 0x10000`** (`0x6c50000`, matching
  the script's first `FLYBY_SET_EVENT_ZOOM -100 10 35`, "fully out"), holds briefly, then swings up to a
  reproducible **maximum of `1976-1977 × 0x10000`** (`0x7b80000`-ish, matching the 3rd keyframe,
  `FLYBY_SET_EVENT_ZOOM 80 165 36`), then eases back down almost exactly to the idle value `1932` by the end
  (matching the 4th keyframe's `FLYBY_SET_EVENT_ZOOM 0 202 63` - zoom=0 maps back to the same value as "no
  zoom at all", i.e. 0 really is neutral, not an arbitrary midpoint).
- **This rules out a simple linear decode of the raw zoom value**: the slope implied by the "out" leg
  (zoom 0→-100 giving raw 1932→1733, Δraw/Δzoom ≈ **+2.0** units of `0x10000` per zoom unit) is wildly
  different from the slope implied by the "in" leg (zoom 0→80 giving raw 1932→1976, Δraw/Δzoom ≈ **+0.55**).
  A single `raw = a + b*zoom` formula cannot produce both. The most likely explanation: this field is not
  the raw keyframe-interpolated value itself but a **smoothed/eased value with its own lag, continuously
  chasing a moving target** - it keeps drifting through what should be a flat "hold" gap between keyframes
  (e.g. between keyframe 2's end and keyframe 3's start it never goes flat, unlike the idle periods before
  the flyby and after keyframe 1), and the "in" leg's lower apparent slope is consistent with it still
  catching up to keyframe 3's target when keyframe 4 already starts pulling it back down. This fits with the
  still-unsolved `+0x30`/`+0x34` candidates above (interpolation progress / easing-acceleration counter) -
  they are plausibly this same smoothing machinery's own internal state, not just along for the ride.
- **Practical consequence**: don't trust a straight-line fit of this channel for a "scale factor" - it will
  silently average over two different effective slopes depending on which leg of which capture it's fit
  against. Solving it for real needs either the actual interpreter/smoothing-function code, or a capture
  precise enough (exact `FLYBY_START`, see "Open questions" #1) to separate "still easing towards keyframe
  N" from "settled at keyframe N's value" before fitting - this session's captures don't have clean settled
  windows for keyframes 2 and 3 to anchor on.
- **UPDATE, same session, follow-up trace: the real AI-script-to-render chain IS found, and corrects the
  bullet above** (an earlier pass through this investigation wrongly ruled `0x41C700` out - it's actually
  the right function, just not used the way first guessed). See the next section for the full chain. Net
  result: `+0x2c`'s own motion (measured above) is confirmed to be driven by something OTHER than the
  zoom-channel chain below - that chain never writes `tribe_struct+0x2c` at all. What `+0x2c` actually is
  remains open; see "Open questions" below.

## The real AI-script zoom chain, traced end to end (does NOT write `tribe_struct+0x2c`)
Starting from `interpret_script`'s (`0x48CC60`, `docs/functions.tsv`) own opcode dispatch table, confirmed
`ai-scripts.md`'s id column IS the real raw opcode id (case index = id − 0x404, table at `0x48E770`) - this
let every `FLYBY_SET_EVENT_*` handler address be read directly instead of guessed. Full chain for
`FLYBY_SET_EVENT_ZOOM` (1211/0x4BB), each link its own `functions.tsv` row:

```text
interpret_script case 0xB7 (0x48E4A2)
  -> 0x490730: resolve 3 operands (value, start, duration), rescale value:
       q8 = -(value * 256) / 100                    # script -100..100 -> Q8.8 +256..-256 (sign flipped)
  -> 0x449240: insert {kind=3, q8, start, duration} into a GLOBAL sorted event table (0x969BE2, 32 slots)
       (shared scheduler - also used by non-flyby timed script/message events, not flyby-exclusive)

0x449320 (per-turn driver, walks the event table once due):
  -> 0x449AE0 (ZOOM "start" callback, fires once at the event's `start` turn):
       q14 = q8 << 6                                 # Q8.8 -> Q14 (256*64=16384=1.0, same scale the
                                                       # camera ROTATION MATRIX uses - "Landscape projection")
       target_delta = q14 - tribe_struct+0x34         # tribe_struct+0x34 CONFIRMED: live signed Q14
                                                       # "zoom channel" accumulator (was an unconfirmed
                                                       # candidate above - now confirmed)
       0x44A070(target_delta, duration, ...)          # sets up a per-tick increment (not traced in detail)
  -> 0x449B30 (ZOOM "tick" callback, every turn while active):
       tribe_struct+0x34 += (per-tick increment); clamp to [-16384, +16384]
       0x41C700(tribe_struct+0x34, 0x4000)            # <- the actual per-tick camera effect
```

`0x41C700` (own `functions.tsv` row, `preset_blend_by_fraction`) is the function this chain actually drives,
every turn, with the live `tribe_struct+0x34` value: it picks the CURRENT named camera preset (table at
`0x88F0C0`, index `0x89C6EE`) and either the next one in the zoom-OUT direction (if the value is positive,
i.e. the script's negative/"out" zoom) or zoom-IN direction (negative value), then linearly interpolates
`result = presetA.field + (presetB.field - presetA.field) * |value| / 16384` into the GLOBAL live render
block (`0x88F004`) for fields `+0x0`(K/bend), `+0x8`, `+0x20`, `+0x2c`, `+0x2e` (word).

**This is a real, fully-confirmed mechanism - but it does NOT touch `+0x10`(D, the actual camera distance
used by the projection formula, "Landscape projection") at all, and it never writes `tribe_struct+0x2c`
(a completely different struct/address from the render block's own `+0x2c`, despite the same small offset -
careful not to conflate them).** So: the flyby's zoom channel visibly changes K/bend and a few other render
parameters by blending between two DISCRETE named camera presets (not a continuous world-unit distance).

## POS and ANGLE channels, also traced - same conclusion, `+0x2c` ruled out of all three
Followed up by tracing the other two main channels through the same per-kind dispatch (`0x449320`'s table at
`0x59CD40`) that ZOOM uses. Both are now fully understood, and neither touches `tribe_struct+0x2c` either -
all three of the flyby's primary channels are now ruled out as its source.

- **POS = kind 1** (`0x490590` queues, `0x449670` start, `0x449760` tick; `functions.tsv`). **Solves the
  former open question "decode the POS waypoints' own coordinate units":** the script's raw x/z values
  (0-255, the queueing code packs each into a single BYTE, which only works if they fit in 0-255 - matches
  the worked example's "252 254" etc. exactly) convert to world/render units via `(cell + 1) * 256` (confirms
  "256 render units per cell", "Landscape projection") - **but "cell" here is NOT the raw byte itself, see the
  correction right below: the raw byte is at HALF-cell resolution over the real map.** The tick callback eases
  two independent float accumulators (x, z) and writes the rounded result straight into `tribe_struct+0x24`
  (x, low word) and `+0x26` (z, high word) - confirms those are exactly what POS drives, nothing else. The
  delta-to-target computation explicitly handles **wraparound on the 16-bit domain** (shortest path across
  the map edge, not a plain subtraction) - the world map wraps, at least as far as camera-focus tracking
  goes.
- **ANGLE = kind 2** (`0x490680` queues, `0x449920` start; `functions.tsv`). Reads the CURRENT yaw straight
  from `tribe_struct+0x32` (the same field the manual mouse-drag rotate function, `0x4429C0`, uses - one
  more confirmation it's the real yaw cell) and the event's raw target angle, computes BOTH possible signed
  deltas around the 2048-unit circle via two angle-delta helpers (`0x4E9B70`/`0x4E9BA0`, not traced), and
  picks one based on a per-event direction-preference byte. **This is `ai-scripts.md`'s documented
  `FLYBY_SET_EVENT_ANGLE` "shortest way" rule, now seen directly in code** - with an explicit override flag,
  so it's not unconditional the way the docs implied.
- **`+0x2c` is still unaccounted for by any of the three primary channels.**

## Correction: POS/TOOLTIP/end-target raw x/z are HALF-cell units, not literal cell indices (found via a user screenshot comparison, not live memory)
The "POS = kind 1" bullet above called the raw script byte a "cell index" - that can't be literally true: the
map (`open-populous::pop3_format::MAP_SIZE`, hard-confirmed against the real `.dat` file's own binary layout,
not a guess) is 128 cells per axis, but level 1's own script uses raw values up to 252/254
(`ai-scripts.md`'s worked example) - over 127, so not a literal 0-127 cell index. This was never actually
checked against the map's real cell count during the original trace (which only cross-checked the "256" scale
factor and the 16-bit wraparound domain against each other, both internal to the exe, never against
`open-populous`'s own 128-cell map).

**Resolution, from a user's own comparison of a level-1 screenshot against `open-populous`'s flyby**: the raw
byte is at HALF-cell resolution across the real 128-cell map - `actual cell = raw / 2`, wrapping at raw=256 /
cell=128. `(cell+1)*256` and "256 render units per cell" both still hold, they just already presume this
halving; the earlier write-up's "plain 0-255 cell indices" framing was an unflagged, uncross-checked
simplification. Three independent checks, all from data already on hand (no new live-memory session needed):

- **Every x/z value in level 1's own script is even**: `FLYBY_SET_EVENT_POS`'s 8/28, 2/28, 252/254, 12/238,
  20/216; `FLYBY_SET_EVENT_TOOLTIP`'s 12/26, 2/250, 18/246; `FLYBY_SET_END_TARGET`'s 20/216 - 11 values, all
  even. Exactly what's expected if the level designer placed every waypoint on a whole real-game cell and the
  compiler doubled it into the script's half-cell encoding; 11/11 landing even by chance alone is ~1/2048.
- `FLYBY_SET_END_TARGET 20 216` halved is cell `(10, 108)` - 1.5 cells from `open-populous`'s own
  independently-derived level-1 site position, `(8.5, 107.5)` (`crates/game-client/src/sites.rs`'s
  `site_cell_pos` test, read straight from the level file's own Thing record - ground truth, not fitted to
  this problem). Matches the original screenshot (camera parked on the stone circle/shaman at the
  reincarnation site, which is also exactly what the flyby's own triggering script logic is about - "FLYBY_START's
  turn" above). Taken 1:1 instead (the raw byte straight into a 128-cell `rem_euclid`, `open-populous`'s
  current `flyby.rs` behaviour) lands at `(20, 88)` - 20+ cells off, out over the sea.
- Consistent with the already-documented "out"/"in" slope asymmetry in the zoom accumulator (next section) -
  not proof by itself, just the same kind of half-scale blind spot this investigation's early passes had more
  than once.

**Practical fix, written up for `open-populous`** (`docs/specs/pop3-rev-analysis.md` "Camera flyby state",
`TODO.md`): `crates/game-client/src/flyby.rs`'s `drive_camera`/`final_pose` currently use the raw
`PosKeyframe`/`EndTarget` x/z bytes unscaled as `CameraRig.focus` cell coordinates (`k.x as f32`, `k.z as f32`,
`end.x as f32`, `end.z as f32`) - each needs `* 0.5` before use. The existing `rem_euclid(MAP_SIZE)`
wraparound is already correct once the halving is applied, no other change needed there. `TOOLTIP` keyframes'
x/z (not currently rendered at all, see "INT_POINT and TOOLTIP channels" below) would need the same halving
whenever that gets implemented.

## Correction: flyby zoom value 0 means "idle", not "midpoint of the manual PITCH_RANGE"
Same user comparison, a second point: the original screenshot's pitch at the flyby's end (last keyframe,
`FLYBY_SET_EVENT_ZOOM 0 202 63` - script zoom value 0) looks shallow, close to the idle ~20.4° view, not
`open-populous`'s `zoom_to_pitch(0)` result (~49.5°, the arithmetic midpoint of manual `PITCH_RANGE`
10.5°..88.6°, `game-client/src/camera.rs`).

This was already implied by two findings in this file, just never connected to `flyby.rs`'s own zoom=0
behaviour: "Zoom channel (`+0x2c`) trajectory..." below found the idle-default raw accumulator (`1932`) is
exactly what script zoom 0 settles back to ("0 really is neutral, not an arbitrary midpoint"), and "Manual
zoom is a pitch+bend orbit" ties that same accumulator/preset system directly to pitch (K and pitch move
together as one input, confirmed live). So script zoom 0 should map to the **idle pitch** (~20.4°, same as
`camera::GROUND_PITCH_DEG`), not `PITCH_RANGE`'s arithmetic midpoint - and since idle sits much closer to the
"zoomed in" end of `PITCH_RANGE` (10.5°) than the "zoomed out" end (88.6°), the real -100..100 -> pitch curve
is asymmetric around 0, not the straight line `flyby.rs::zoom_to_pitch` currently implements. Consistent with
the already-documented "out"/"in" slope asymmetry in the raw zoom accumulator (Δraw/Δzoom ≈ +2.0 "out" vs
+0.55 "in" per zoom unit) - same lopsidedness, seen from a different angle. **Not yet solved**: the actual
curve shape between the two confirmed endpoints and this new zoom=0 anchor - three points constrain it, they
don't determine it. Written up for `open-populous` in `pop3-rev-analysis.md`/`TODO.md`.

## INT_POINT and TOOLTIP channels traced - neither writes `+0x2c` either, but TOOLTIP's timing correlates
Followed up on the user's own observation (playing level 1: a building/pyramid is presented and a tooltip
pops up on it at the same time as what felt like a camera distance change). Traced the remaining two
channels (kind 4 and 5 in the same `0x59CD40` table):

- **`INT_POINT` = kind 4** (`0x4907F0` queues, `0x449C40` start, `0x449D80` tick; `functions.tsv`). This is
  a "look at this point" channel: it computes the angle from the CURRENT camera focus to a target (x,z) cell
  (same `(cell+1)*256` conversion as `POS`, via the angle-from-vector helper `0x586074`) and continuously
  eases the yaw (`tribe_struct+0x32`) toward it, RE-AIMING every tick as the focus itself moves (not a fixed
  target angle) - genuinely "turn to face the building." **But level 1's own script never uses it**
  (`ai-scripts.md`'s usage count for `FLYBY_SET_EVENT_INT_POINT` is 0/0) - ruled out for this specific
  observation, though it's a real, confirmed mechanism other levels may use.
- **`TOOLTIP` = kind 5** (`0x490970`/entry `0x4908E0` queues, `0x44A030` start -> `0x44D7F0`; `functions.tsv`).
  `0x44A030`/`0x44D7F0` turned out to be a GENERIC "register a categorised notification" system also used by
  the ordinary advisor-message path (`fire_advisor_message_once`), not flyby-specific - the script's own
  `idx` argument (0 or 1) selects category 1 or 2. **Category 1 (`idx=0`) walks a linked chain of "head"/
  monument-type scenery objects near the given point and displays the one it finds - this is almost certainly
  the exact "a building/pyramid is presented" behaviour reported for level 1** (whose 3rd tooltip uses
  `idx=0`); category 2 (`idx=1`, the other two) resolves a specific object by id and, if it belongs to a
  tribe, additionally draws a small tribe-coloured indicator.

**Followed the render side too**: the record `0x44D7F0` writes is read every frame by `render_land_ui_1`
(`0x44A34D`, own row, found this session) to actually draw the popup - it projects the target point through
the normal camera matrix (`coord_global_convert`), offsets the label anchor sideways, and applies screen
coordinate conversions. **Confirmed: NEITHER `0x44D7F0` NOR `render_land_ui_1` writes `tribe_struct+0x2c`,
the render-block D field, or the `0x89CE34` transition counter anywhere.** The full tooltip pipeline, both
creation and rendering, is now fully traced and does not move the camera at all, directly or via the
preset-transition system.

**So the timing correlation that motivated this detour is not explained by this code path.** Level 1's 3
`FLYBY_SET_EVENT_TOOLTIP` windows (with `FLYBY_START` now known exactly as turn 72: `[132,203]`, `[204,264]`,
`[265,325]`, contiguous) still line up with `+0x2c`'s own long unbroken rise phase (`cam5.txt`, turn ~156 to
~303-314) far better than `ZOOM`'s gappy schedule does - that observation stands. But it is NOT because
showing a tooltip triggers a camera effect; if the correlation is real rather than coincidental, the actual
cause is still completely unknown. Don't re-chase the tooltip/message pipeline for this again - it's a
confirmed dead end now, checked from both the creation and the rendering side.

## `tribe_struct+0x2c` solved: it's not a real field, just two adjacent ones aliased by the scan (open question #6, CLOSED)
Found via a live GDB hardware write-watchpoint on the computed address (`0x89D1C8+tribe*0xC65+0x2c`,
tribe=0 confirmed live), run through a fresh full flyby inside the headless Docker/Xvfb rig (gdb
added to `docker/Dockerfile` this session) - the static-grep approach camera.md's own "Open
questions" #6 flagged as exhausted finally has a live tool now (`scripts/watch_addr.py` +
`scripts/docker/watch_addr.sh`, generic reusable hardware-watchpoint helper, added this session).
216 of 218 hits captured landed on the exact same instruction.

**The "+0x2c dword" `--scan-tribe` was ever reporting never existed as its own field.** `--scan-tribe`
reads the tribe_struct range as 4-byte-aligned dwords, so what it calls "+0x2c" is just
`bytes[+0x2c..+0x2f]` read as one little-endian int. Those 4 bytes are actually the tail end of TWO
unrelated, independently-written fields:

- `tribe_struct+0x2a` (dword, bytes `+0x2a..+0x2d`): a straight per-tribe, per-frame COPY of the
  GLOBAL render block's own `+0x8` field (`0x88F00C`, one of the 5 fields `0x41C700`/
  `preset_blend_by_fraction` blends every tick for the flyby's ZOOM channel - `functions.tsv`'s own
  row for it). Live-confirmed this session: this value stays small (observed `0x9F52`, well under
  `0x10000`), so its own high word - which is exactly `tribe_struct`'s bytes `+0x2c/+0x2d`, the "low
  half" the scan tool was reporting as part of "+0x2c" - is normally `0`. That's the entire
  explanation for the old "always an exact multiple of `0x10000`" observation: the low half of the
  scanned dword is just unrelated padding from a DIFFERENT field that happens to stay small.
- `tribe_struct+0x2e` (word, bytes `+0x2e/+0x2f` - the scanned dword's HIGH half, i.e. the part that
  actually carries the signal): a straight per-tribe, per-frame copy of the render block's own
  `+0x20` field (`0x88F024`), ALSO one of `0x41C700`'s 5 blended fields. Live-confirmed exactly:
  read simultaneously mid-session, `tribe_struct+0x2e == render_block+0x20 == 1932` (the documented
  idle value) to the integer.

Both copies happen in the same function, found this session: `set_player_transform_matrix`
(`0x47F480`, name from `backup.xml`'s own Ghidra `FUNCTION` entry, role now independently
traced - `functions.tsv`'s own row has the full breakdown). It's called from `update_vfconfig`
(`0x417338`, two call sites inside that same function, `0x41744F`/`0x417462`) - the SAME per-tribe,
per-frame routine already confirmed to rebuild the camera matrix pointer - plus a handful of other
call sites not individually checked this session (`0x417967`, `0x41C98D`, `0x41C9A1`, `0x4A4B5B`).
So this isn't a flyby-specific write at all; it runs every frame regardless, for whichever tribe is
being updated, which is exactly why none of the five flyby channels (or the tooltip pipeline) were
ever found writing it directly - they don't need to. They only have to move the render block's own
`+0x20`/`+0x8` fields (which `0x41C700` already does, confirmed), and this copy function mirrors
whatever those currently are into the tribe's own saved state every frame, unconditionally.

**This resolves "remaining lead (b)" from the old open-questions list exactly** ("`+0x2c` as a
passively-updated mirror of [...] some other already-tracked value computed once per frame
elsewhere, independent of any flyby channel") - just not of `D`; of the render block's own
`+0x20`/`+0x8`, two fields that were already-named-but-unconnected-to-tribe_struct `0x41C700`
outputs. The `TOOLTIP`-timing correlation ("INT_POINT and TOOLTIP channels" above) is explained the
same indirect way: both `+0x2e`'s motion and the tooltip windows happen to fall inside the flyby's
own ZOOM-channel-driven preset blend, with no direct causal link between tooltips and the camera -
consistent with that section's own finding that the tooltip pipeline never touches any camera field.

**New, smaller leads opened by this trace, not pursued further this session**: `set_player_transform_matrix`
also conditionally calls `rotate_main_cam`/`0x4429C0` (own row) with a delta read from a global
object's own `+0x88` byte, gated on flag `0x89D17C`&0x2 being CLEAR and a global pointer `0x96AA70`
being non-null - looks like some kind of automatic/scripted camera-nudge path distinct from both the
manual mouse-drag handlers and the flyby channels, not identified. It also calls `0x42A070` and
`0x47FAB0` (twice, with the current yaw `tribe_struct+0x32` and the negated `+0x2e` value as
arguments) - neither traced this session.

## The `0x44A070` ease-setup helper (open question #7, mostly solved)
Traced statically (pure disassembly + reading the two literal float constants it multiplies by out of
the exe's `.rdata`, no live memory needed) - the shared "ease toward a target" setup every flyby channel's
`start` callback calls (`0x449670` POS, `0x449920` ANGLE, `0x449AE0` ZOOM, `0x449C40` INT_POINT - all own
`functions.tsv` rows). Own row added: `0x44A070`.

- **Signature**: `fn(delta: i32, duration: i32, state: *EaseState, out: *f32x2)`.
- **One contiguous state block, not two separate pointers**: the ZOOM call site passes `&0x969D52` for
  `state` and `&0x969D66` for `out` - exactly `0x14` (20) bytes apart, matching the state block's own
  written size. So `out` is just `state+0x14`, the same per-channel blob `functions.tsv`'s `0x449B30` row
  already named as "per-tick state at `0x969D52`/`0x969D5A`/`0x969D66`."
- **Velocity continuity, not a reset**: `state`'s existing "current rate" field (read back in, not
  zeroed) feeds the new computation - re-triggering an ease mid-motion blends from the camera's current
  rate rather than snapping to a fresh start, consistent with this exe's camera generally avoiding
  discontinuities (matches the manual-pan momentum system noted in "Mouse-drag camera" above, a different
  but thematically similar smoothing habit).
- **Duration scaling**: `duration` gets multiplied by two literal constants read directly from `.rdata`
  (`0x58F2FC` = 64.0, `0x58F300` = 1/256; product = 0.25 exactly) and floored at a minimum of 1.0 - i.e.
  the usable tick budget is a quarter of the raw `duration` argument, never less than one tick. Not yet
  tied to a known subtick/frame-rate constant elsewhere in the exe; a plausible explanation (not confirmed)
  is that `duration` arrives already expressed in a 4x-finer unit than the budget this function actually
  steps in.
- **Kinematic branch**: computes a "stopping distance" threshold from the carried-over rate using the
  standard constant-deceleration formula `rate² / (2·accel)`, then branches on whether `delta`'s magnitude
  is inside or outside that threshold - i.e. "can the current rate already get there without overshoot."
  Inside -> single flat rate `delta/duration` (no accel/decel phase, two of the output fields zeroed).
  Outside -> a two-phase accelerate/decelerate profile, duration split into a "time to kill the existing
  rate" piece and a remaining piece - this session didn't re-derive the exact blend past that split point
  (several chained adds/subtracts/divides combine duration, the stop-time, and the scaled-duration value
  into final phase lengths/rates - plausible but not confirmed to be a textbook trapezoidal/S-curve profile).
- **Practical read for `flyby.rs` parity**: this confirms the original's ease is NOT a plain
  lerp/smoothstep over `[start, start+duration]` the way `open-populous` likely assumes - it's a
  kinematic, rate-continuous accelerate/decelerate profile that also depends on whatever rate the channel
  already had going in. The "Joint fit" section above tried plain linear/smoothstep curves and got
  R²~0.1-0.6, never a clean fit - this finding explains why: neither curve family is the right shape in the
  first place.

## Manual zoom (`+`/`-`) is a pitch+bend orbit, not a distance dolly
Live test, this session (headless Docker/Xvfb, in normal post-flyby free play, not a flyby):
held the zoom-out and zoom-in keys and logged `D`/`K`/`S`/the matrix via `watch_camera.py`'s fixed
field list (not `--scan-tribe` this time - these fields were already in `FIELDS`). Across the
**entire** zoom range - from the idle ground view, down through the documented flyby-dive pitch
(~-55°), all the way out to the iconic Populous "whole-planet globe" view (~-88.6° pitch, confirmed
on screen, a real screenshot of the planet floating in space) - **`D` (0x87CA64) and `S` (0x87CA68)
never moved once, staying exactly 6500 and 11 for the whole test.** Only the matrix's own pitch
(`M21`/`+0x1C`) and `K` (0x87CA5C, bend) moved, together, monotonically, and fully reversibly:

```
K        pitch     notes
 46000   -20.39°   idle default (matches "Landscape projection"'s own documented K/pitch exactly)
 38000   -24.61°
 28000   -31.82°
 16000   -41.31°
  4000   -50.80°
     0   -55.55°   K floors out here...
     0   -66.09°   ...but pitch keeps steepening while K stays pinned at 0
     0   -88.58°   whole-planet globe view (screenshot-confirmed), D and S still 6500/11
     0   -55.55°   (zooming back in) K still 0 here, pitch already back to the flyby-dive value
  3680   -54.14°   K starts moving again
 46000   -20.39°   idle reproduced exactly on the way back through
 58800   -10.54°   zooming further "in" than idle: pitch keeps going shallower, K keeps rising
                   past its own default - idle is a point mid-curve, not an endpoint
```

- **Corrects "Landscape projection"'s own `M` row** ("pitch fixed at about 20.4° ... while the
  player drives the camera - varies during AI-script flybys"): pitch is NOT fixed during ordinary
  manual play either - it only looks fixed because nobody was zooming. The flyby's own ~-55° dive
  (see "Pitch is not a fixed per-game constant" above) passes through essentially the same pitch
  value manual zoom-out reaches on its own way out to the globe view - consistent with both sharing
  the same small preset table via `0x41C700`/`preset_blend_by_fraction` (already traced for the
  flyby's `ZOOM` channel, "The real AI-script zoom chain" above).
- K saturating at 0 while pitch keeps moving (and vice versa not observed - they never visibly
  decouple at the idle-ward end) confirms K and pitch are two independently-moving outputs of
  whatever single "zoom level" input drives both, not one computed from the other by a fixed
  formula.
- **This empirically confirms, with live round-trip data rather than just the statically-traced
  flyby chain, the architectural point behind `open-populous` `TODO.md`'s existing "`zoom_to_distance`
  may have the wrong shape entirely" note**: at every level the real engine's "zoom" - manual play
  and flyby script alike - orbits the camera's pitch around a (so far, in this test) constant-radius
  arc and reshapes K/bend; it never moves the literal camera-distance register `D`.
- Not yet measured: whether `D` is EVER non-constant anywhere in the real game (a mod/cheat, a
  different level, combat zoom, etc.), or what exactly happens to `tribe_struct+0x2c` (the still-
  unexplained field, open question 6) during this same manual-zoom sequence - worth a `--scan-tribe`
  capture through the same `-`/`=` sequence as a natural follow-up.

### Headless keyboard reliability (practical note for future sessions)
`xdotool key plus` / `key minus` (and `keydown`/`keyup` the same) do **not** reliably reach the game
for the shifted `+` character - only `-`/`minus` worked directly; zoom-IN only started working once
sent as `equal` (the bare, unshifted physical key) instead of `plus` (which needs a synthesized
Shift that this Wine/XTest setup doesn't deliver through to the game's DirectInput polling).
Plain arrow keys (rotate) worked fine either way. No explicit window activation was needed once the
game window existed (`xdotool search --name ""` + `getwindowname` to find it, e.g. "Populous, The
Beginning" - there's no window manager here to report an "active" window, but plain `xdotool key`
without `--window` still reached it).

## D3D axis caveat (flagged by the user, not yet applied)
D3D's coordinate convention is left-handed, differing from `open-populous`'s own engine, at least on
the Z axis. Any of the candidates above, once their scale/offset is pinned down, will need an
explicit axis/handedness conversion before they're used to correct `flyby.rs` or written as settled
facts - don't treat raw fitted constants as drop-in. One concrete instance already found: the
matrix's pitch sign came out flipped relative to how `pop3-rev-analysis.md`'s "Landscape projection"
used to state the pitch constants (now corrected there).

## D3D axis caveat for YAW - RESOLVED for the ANGLE channel: `open-populous`'s existing mirror convention is already correct
Open question 5 (apply the D3D axis caveat to yaw) is now answered for the flyby `ANGLE` channel specifically,
using a model the user proposed (`yaw_true = s * raw * 360/2048 + c`, needing >=2 independent raw/true-yaw pairs
to pin down `s` and `c` - one point can't separate scale from offset) and data already on hand, no new live
session needed.

**Why the earlier "~180 deg apart" note (under "The intro message dialog pauses...", above) was inconclusive,
not wrong**: that comparison used the raw NAIVE conversion (`raw * 360/2048`, no sign flip) against the one
live-measured final yaw (~107.8 deg) and eyeballed a rough 180 deg gap - exactly the single-point situation the
user's model describes, where a scale/sign error and an offset error look alike. It was never a screenshot/focus
comparison (it compares the real exe's OWN live matrix yaw to the script's OWN raw angle number, nothing about
`open-populous`'s rendering or focus position), so the recent POS/focus-scale fix (two sections above) doesn't
apply here and can't make this discrepancy "disappear" the way it might for a screenshot-based comparison -
it needed real resolution, not a re-check.

**Resolution**: re-parsed `cam7.txt` and `cam5.txt` (both already-captured, turn-anchored full-flyby runs,
independent sessions) for the matrix's own decoded yaw (`atan2(M02, M00)`, unwrapped/accumulated across turns
to avoid false wrap-artifacts) and found genuine flat holds (slope < 0.15 deg/turn over >=4 samples - stricter
than a simple "small window variance" test, which false-positives on slow continuous creep) at four points each,
landing **in the same order as the script's own six `FLYBY_SET_EVENT_ANGLE` keyframes** (`ai-scripts.md`'s
worked example: raw 0, 1072, 681, 744, 54, 1438 - the middle two, 1072 and 54, only ever get a brief partial
approach before the next keyframe preempts them, consistent with their own 1-turn script gaps, too tight to
fully settle; the other four get a real multi-turn hold):

| raw (script) | predicted, `s=-1, c=0` (`-raw * 360/2048 mod 360`) | `cam7.txt` observed (turns) | `cam5.txt` observed (turns) |
|---|---|---|---|
| 0 | 0.00 | 359.65 (127-137) | 357.89 (119-128) |
| 681 | 240.29 | 244.31 (248-258) | 237.30 (232-243) |
| 744 | 229.22 | 232.20 (296-302) | 227.98 (271-280) |
| 1438 (final) | 107.23 | 106.52 (426-438) | 107.75 (392-404) |

Every point lands within **~0.5-4 deg** of `s=-1, c=0` in BOTH independent captures - i.e. **`yaw_true = -raw *
360/2048 (mod 360)`**, a pure sign flip, no offset. The `s=+1` (no flip) hypothesis is decisively refuted by the
same data: it predicts 119.71/130.78/252.77 deg for the three non-trivial points, 100-150 deg off every single
one (this is exactly the stale "~180 deg apart" observation, now explained: the naive conversion is just the
wrong sign). The residual few-degree spread between the two captures (e.g. 244.31 vs 237.30 for raw=681) is
consistent with "approaching but not perfectly settled when sampled" (the still-unsolved two-phase kinematic
ease, "The `0x44A070` ease-setup helper" above) rather than an unmodeled constant offset - `c=0` already fits
the trivial `raw=0` point and the unambiguous final hold (`raw=1438`, nothing queued after it, no preemption
possible) equally well in both captures.

**This confirms `open-populous`'s EXISTING code is already right, no fix needed**: `game-client/src/flyby.rs`'s
`render_yaw` calls `nature::angle_yaw(raw).render()`, and `GameYaw::render()` (`game_frame.rs`) already negates
(`-self.0`) as the documented general left-handed-to-right-handed mirror ("the files, `game-core` and the
original models use [the game's left-handed frame]... Bevy is right-handed... these types... mirror z"). That
generic convention, applied to the flyby's `ANGLE` channel specifically, is exactly the `s=-1, c=0` this session
derived from live data - a genuine cross-check (the mirror convention was derived independently, for a different
reason, long before this session), not a coincidence tuned to fit. **Step 1 of the user's own methodology
(settle mirroring first, from landmark ordering) is answered the same way, just via live-memory numbers instead
of a screenshot**: the mirror is confirmed real and already implemented correctly for yaw.

Not re-checked: whether the SAME left-handed/right-handed mirror convention needs applying anywhere else this
investigation's candidates touch (position/focus does not - "Correction: POS/TOOLTIP/end-target..." above
already covers the only remaining x/z scale issue, and cell coordinates don't carry a handedness sign the way
an angle does). Pitch's sign was already separately corrected ("Landscape projection", above).

## `flyby.rs::zoom_to_pitch` calibrated against the same traces - the script's -100..100 does NOT span `PITCH_RANGE`
Same extraction pipeline as the `ANGLE` cross-check above (flat-hold detection, slope < 0.15 deg/turn over >=4
samples), run against `cam5.txt`/`cam7.txt`'s matrix pitch (`M21` at `+0x1c`, `pitch = asin(M21/16384)`) instead
of yaw, matched in temporal order to level 1's own four `FLYBY_SET_EVENT_ZOOM` keyframes
(`-100 10 35`, `10 67 25`, `80 165 36`, `0 202 63`, from `ai-scripts.md`'s worked example):

| zoom (script) | `cam7.txt` observed hold (turns) | `cam5.txt` observed hold (turns) |
|---|---|---|
| -100 ("fully out") | -55.37 deg (134-165) | -55.37 deg (126-154) |
| 10 | -19.51 deg (196-298) | -19.51 deg (183-276) |
| 80 | ~-12.7 deg (340-352) | -12.69 deg (311-322) |
| 0 (final) | -20.56 deg (425-437) | -20.57 deg (390-403) |

Agreement between the two independent captures is tight (<=0.3 deg on every point, tighter even than the `ANGLE`
cross-check) - the zoom channel's own mechanism (a direct accumulator -> `preset_blend_by_fraction`, "The real
AI-script zoom chain" above) is evidently cleaner/more deterministic than `ANGLE`'s shortest-path kinematic ease.

**Confirms last session's "zoom 0 = idle" hypothesis exactly**: the final hold (-20.56/-20.57 deg) matches the
idle default (-20.39 deg, `camera::GROUND_PITCH_DEG`) to within 0.2 deg - not `zoom_to_pitch(0)`'s current
~49.55 deg (`PITCH_RANGE`'s arithmetic midpoint).

**New, bigger finding: the script's own -100..100 domain never reaches anywhere near `PITCH_RANGE`'s own
endpoints (10.5/88.6 deg)**. Comparing every point against the current `zoom_to_pitch` formula:

| zoom | `zoom_to_pitch` (current) | observed | error |
|---|---|---|---|
| -100 | 88.60 | 55.37 | 33.2 deg |
| 10 | 45.64 | 19.51 | 26.1 deg |
| 80 | 18.31 | 12.70 | 5.6 deg |
| 0 | 49.55 | 20.56 | 29.0 deg |

Every point is wrong, not just the zero-point - `PITCH_RANGE` (10.5-88.6 deg) is real (confirmed live, "Manual
zoom is a pitch+bend orbit" above) but it's the range reachable by HOLDING THE MANUAL ZOOM KEY all the way to
the whole-planet globe view, a completely different input than the AI script's bounded `-100..100` argument -
conflating the two was the actual bug, not just a wrong offset. The script's own practical range for level 1
is roughly -55.4 deg (at script -100) to -12.7 deg (at script 80, the largest "in" value this script happens to
use) through an idle default of -20.4 deg at script 0 - narrower, and not centred the way `PITCH_RANGE`'s
10.5-88.6 deg midpoint-at-zero assumption implied.

**The out/in slope asymmetry already documented for the raw zoom accumulator (`+0x2c` trajectory, "Zoom channel
(`+0x2c`) trajectory..." above, out ~2.0 vs in ~0.55 per zoom unit, ratio ~3.6) reproduces almost exactly in
pitch-degree units too**: out leg (-100 -> 0) slope = (20.4-55.37)/100 = 0.35 deg/zoom-unit; in leg (10 -> 80)
slope = (19.51-12.70)/70 = 0.097 deg/zoom-unit; ratio 0.35/0.097 ~ 3.6 - the same asymmetric curve shape, seen
directly in the quantity that actually matters for `flyby.rs` (degrees) instead of the internal accumulator
units, and independently cross-validating both findings against each other.

**Eye-to-focus distance (`D`) - not testable from these traces, already settled two other ways**: `cam5.txt`/
`cam7.txt` are `--scan-tribe` runs of `tribe_struct` only; `D` (`0x87CA64`) lives in a separate global
render-block struct, never captured there. Two independent, already-existing findings settle it instead: (1) a
live round-trip manual-zoom test, a DIFFERENT capture ("Manual zoom is a pitch+bend orbit" above), found `D`
and `S` "never moved once" across the entire zoom range, idle through the whole-planet globe view; (2) the
flyby's own `ZOOM` opcode chain was traced statically start to finish ("The real AI-script zoom chain" above)
and confirmed it "does NOT touch `+0x10`(D)... at all" - a code-level guarantee, not just an observation. Zoom
(manual and scripted alike) drives pitch and K/bend only, never distance - already fully confirmed, no new
capture needed to answer this part.

**Practical fix for `flyby.rs`**: `zoom_to_pitch` needs its target values replaced, not just its zero-point -
the table above gives 4 real (zoom, pitch) pairs to fit against instead of the two manual-zoom endpoints alone
(which describe a different input entirely). A 3-segment piecewise curve (or similar) through
`(-100,-55.4) (0,-20.4) (10,-19.5) (80,-12.7)` would already match this level's own script far better than the
current single linear span across `PITCH_RANGE`; more data points (other levels' own flyby scripts, run through
the same pipeline) would pin the shape further, especially past zoom=80 up to 100, not exercised by level 1's
own script. Written up for `open-populous` in `TODO.md`/`pop3-rev-analysis.md`.

## Distance vs. FOV: `open-populous`'s `D=25.4 cells` is measured, `DEFAULT_FOV=35 deg` is an admitted guess - and there's a second, untraced camera-distance mechanism
User's own instinct (comparing the original screenshot's strong foreground perspective against `open-populous`'s
flatter render) was that distance "feels like it should be ~10 [cells]", with the caveat that distance and FOV
are confounded in a single still image (on-screen size scales with `1/(distance * tan(fov/2))`). Worth separating
what's actually measured from what's guessed before touching either number:

- **This exe's landscape renderer does NOT use a standard D3D perspective matrix at all** - "Landscape
  projection" (`pop3-rev-analysis.md`) already documents the real formula, a bespoke fixed-point integer
  pipeline: `screen = (x', y') * (1 << (S+16)) / z'` after the rotation+bend+distance steps. There is no `P[1][1]
  = 1/tan(fov_y/2)` matrix to read `fov` off - the closest equivalent is `S` ("perspective shift", measured
  default 11), which acts as a focal-length-like scale exponent, not an angle.
- **`D` (camera distance) is one of the best-confirmed numbers in this whole investigation, not a guess**: measured
  live as exactly 6500 render units (25.4 cells) behind the focus, and independently confirmed CONSTANT two
  separate ways - a live round-trip manual-zoom test across the ENTIRE range (idle through the literal
  whole-planet globe view, screenshot-confirmed) never moved it, and the flyby's own `ZOOM` opcode chain
  (`0x41c700`/`preset_blend_by_fraction`, `functions.tsv`) was traced statically and explicitly does NOT touch
  `+0x10`(D) among the 5 render-block fields it does blend. Both findings predate this session; neither was
  derived to answer this question, which is why they're decent independent evidence rather than a fit tuned to
  match.
- **By contrast, `open-populous`'s own `DEFAULT_FOV = 35 deg` is admittedly NOT measured from the exe at all** -
  its own code comment: "not traced in the original (its screen scale is open); 35 deg frames at 25.4 cells what
  a view matched by eye on level 23 framed at 13.8 cells and 60 deg." Given `D` is hard-measured and `FOV` is an
  eyeballed guess, a perspective mismatch is much more likely to be a wrong FOV than a wrong distance - exactly
  the alternative the user's own math flagged (FOV~77 deg at distance 10 would look the same as the current
  guess at distance 25.4, so "distance feels wrong" doesn't by itself tell you which one actually is).
- **Deriving `S`'s equivalent FOV needs one more piece this investigation hasn't pinned down**: "Landscape
  projection" already flags it - `screen = (x',y') * (1<<(S+16))/z'` is an INTERMEDIATE value, not final pixels;
  there's "a per-axis screen scale" applied after this step that converts it to actual screen coordinates,
  explicitly noted as "not checked." Without that scale (and the exe's actual render resolution), `2^(S+16)`
  alone isn't convertible to a focal length in the same units as screen half-width, so an equivalent FOV in
  degrees can't be computed with confidence yet - this is real remaining work, not a number to guess at.
- **New lead, found in `functions.tsv` while checking this, not yet connected to the flyby investigation
  before now**: there IS a second, separate camera-preset-blend mechanism, `0x417510` ("Camera-PRESET
  multi-frame blend", own row), confirmed to blend `D` (`0x88F014`) AND `S` (`0x88F018`) - fields the flyby's
  own `0x41c700` explicitly does NOT touch. It's a multi-FRAME ease (driven by a frame counter at `0x89CE34`,
  not the flyby's 0..1 fraction argument), and `functions.tsv`'s own note says its trigger is "still unclear...
  plausibly `CREATE_MSG_INFORMATION_ZOOM`, not confirmed." `open-populous`'s own `ai-scripts.md` independently
  documents `CREATE_MSG_INFORMATION_ZOOM idx x z angle` as a script opcode that "also zooms the camera while the
  message is open" - a genuinely different, as-yet-untraced camera effect from the `FLYBY_SET_EVENT_ZOOM` channel
  this whole investigation has been about. **If the screenshot being compared was taken at a moment touched by
  this other opcode (or `ZOOM_TO`/`TRACK_TO_MARKER`, also listed in `ai-scripts.md`, also untraced) rather than
  purely the flyby's own channel, distance really could move - just via a code path nothing here has looked at
  yet.**
- **Checked, a later session, RULED OUT for level 1 specifically**: the user supplied the actual game install
  (`.../Bullfrog/Populous - A l'aube de la création/levels/cpscr010.dat`), so this could finally be checked for
  real via `cargo run -p pop3-ai-script --example ai_script_info -- <path>`. The full parsed AST of level 1's own
  red-tribe script contains **exactly one `Flyby` node** (matching the already-documented worked example, no
  second flyby) and **zero occurrences anywhere in the entire script** of `ZOOM_TO` (1111),
  `TRACK_SHAMAN_TO_ANGLE` (1133), `TRACK_TO_MARKER` (1152), `CREATE_MSG_INFORMATION_ZOOM` (1177), or any of the
  other `SET_MSG_*ZOOM*` opcodes (1178/1182/1183/1184/1186) - confirmed by listing every distinct `CommandId`
  the parsed script actually uses and diffing against that list. **So the "other mechanism" lead is dead for this
  specific screenshot**: whatever camera behaviour the original shows at the end of level 1's intro is driven
  purely by `FLYBY_SET_EVENT_ZOOM`, already fully traced (above) and confirmed to never touch `D`. The distance/
  FOV mismatch, if real, isn't explained by a different script opcode - it comes down to `open-populous`'s own
  `DEFAULT_FOV` guess (next bullet), or a genuinely unmodelled part of the already-documented projection formula
  (the missing per-axis screen scale), not a missed camera-control code path.
- **Practical recommendation (superseded below, kept for context)**: don't change `GROUND_DISTANCE`/`D` off a
  screenshot read alone - still true. The per-axis screen-scale gap this bullet used to list as open is now
  solved - see the next two sections.

## The per-axis screen scale SOLVED: static disassembly of the projection's final step (no live memory needed)
Found by disassembling `0x46de00` (per-vertex projection with the planet bend, `functions.tsv`'s own minimal
row) and its setup function `0x5215b3`-ish (unnamed, writes the `+0xcf8`/`+0xcfc` fields read here), using the
`exe-function-map`-style toolchain (`setup.sh`+`sl.py` run directly, the skill itself disabled for model
invocation this session but its scripts work standalone) - the user handed over the real game install
(`.../Bullfrog/Populous - A l'aube de la création/`), closing what "Landscape projection"'s own note flagged
as unchecked.

**Full pipeline, past where `pop3-rev-analysis.md` previously stopped** (`(x',y',z')` = the already-documented
rotated+bent point, `z' += D` already applied):

```text
Q = tribe_struct+0x2a                          # CONFIRMED: this IS render-block+0x8's per-frame mirror,
                                                 # previously just "the camera focus"-adjacent dword from
                                                 # "Correction: POS/TOOLTIP..." above - wrong structure, same
                                                 # offset by coincidence; this Q is a DIFFERENT value,
                                                 # read directly off the active tribe's own tribe_struct
shiftA, shiftB = byte[cf8_struct+0xcf8], byte[cf8_struct+0xcfc]   # per-axis, chosen at startup from
                                                                     # video-mode flags, see below
X2 = (x' * Q) >> (16 - shiftA)                 # intermediate, per-axis
Y2 = (y' * Q) >> (16 - shiftB)
scale_persp = (1 << (S+16)) / z'                # the already-documented step, SHARED by both axes
finalX_int = (X2 * scale_persp) >> 16
finalY_int = (Y2 * scale_persp) >> 16
scaleX = 1.0 / (1 << shiftA)                    # float, precomputed once at startup (same cf8_struct)
scaleY = 1.0 / (1 << shiftB)                     # ( * a literal float constant at 0x58fc4c, confirmed = 1.0
                                                   #   exactly - reads straight out of .rdata, no live memory
                                                   #   needed for this one)
screen_x = origin_x + finalX_int * scaleX        # final output, written into the point struct
screen_y = origin_y - finalY_int * scaleY        # Y is SUBTRACTED (screen-down vs math-up convention)
```

**The per-axis split (`shiftA`/`shiftB`) algebraically CANCELS OUT of the final result** - substitute `X2`
into `finalX_int` into `screen_x` and the `2^shiftA` terms cancel exactly (confirmed both symbolically and by
hand-computing a concrete example: `x'=3250, Q=40786, z'=D=6500`, with `shiftA=4` giving `screen_x-origin_x
≈637.4` and with `shiftA=0` giving `≈637.1` - same answer to rounding). **So "Landscape projection"'s old
"assuming the screen scales both axes alike (per-axis screen shifts not checked)" is now CONFIRMED TRUE**: X
and Y share one real scale factor, `focal = Q * 2^(S-16)` (in screen pixels), despite the per-axis plumbing -
this isn't an anisotropic lens, the `shiftA`/`shiftB` split is just an internal fixed-point precision choice
(confirmed different per video-mode class via `[esi+0x8]` bits `0x20`/`0x40` and `[cf8_struct+0x640]==2`, not
worth chasing further since it's provably inert on the output).

**Concrete numbers, this session**: render-block defaults (`0x416f50`, hardcoded literals, read directly from
the exe - matches every live-read default exactly: `K=0xb3b0=46000`, `D=0x1964=6500`, `S=0xb=11`, and **`Q
(+0x8) = 0x9f52 = 40786`**, confirmed live too). At idle: `focal = 40786 * 2^(11-16) = 40786/32 = 1274.56`
screen pixels. The game's own render window (confirmed both statically - `0x416f50` also hardcodes a `640,480`
pair at `+0x30/+0x32` right next to K/D/S/Q - and live, `screen_w`/`screen_h` globals at `0x89c6cf`/`0x89c6d1`
read exactly `640`/`480` in this session's headless capture) gives, at idle:

```text
FOV_y = 2*atan(240 / 1274.56) = 21.3 deg     (half-height 240 = 480/2)
FOV_x = 2*atan(320 / 1274.56) = 28.2 deg     (half-width 320 = 640/2)
```

**This is NARROWER than `open-populous`'s current `DEFAULT_FOV=35 deg` guess, not wider** - the opposite
direction from the "distance~10, wide FOV" hypothesis this investigation started from (see "Distance vs. FOV"
above). But that idle number isn't the whole story - see the next section, which is the actual answer to "is it
distance or FOV": **it's FOV, and it moves a lot more than just between idle and some fixed constant.**

`origin_x`/`origin_y` (where `(0,0)` camera-space lands on screen): traced to `origin_x = render_block+0x2a +
screen_width/2`, `origin_y = render_block+0x2c + screen_height/2` (`clear_land_draw_state`/`0x46e700`, the
same per-frame copy function already in `functions.tsv`). **Y matches live exactly**: `render_block+0x2c=16`,
`screen_height/2=240` -> predicted `256`, observed (live) `origin_y=256`. **X does NOT match**: `render_block
+0x2a=0` (confirmed live, never changes) + `320` predicts `320`, but live `origin_x` reads `270` throughout -
a constant, unexplained ~50px discrepancy, not yet resolved (doesn't affect the FOV number above, which is
independent of origin - only affects exactly where screen-center sits). Worth a dedicated follow-up: either a
second write site overrides `origin_x` specifically (UI-sidebar related, the 640-wide window's left ~90px are
UI chrome - a plausible but unconfirmed culprit), or this capture's `render_block+0x2a` read was stale/wrong.

## Zoom changes effective FOV too, confirmed live - "pitch+bend orbit" was incomplete, not wrong
**`render_block+0x8` (this session's `Q`, i.e. the focal-length factor above) and `render_block+0x2c` (the
`origin_y` term above) are TWO of the five fields `0x41c700`/`preset_blend_by_fraction` already blends for the
flyby's `ZOOM` channel** (`functions.tsv`'s own row for `0x41c700` lists `+0x0(K) +0x8(unnamed) +0x20(unnamed)
+0x2c(unnamed) +0x2e(unnamed)` - `+0x8` and `+0x2c` are now named; `+0x20`/`+0x2e` remain open). Live-confirmed
this session (`scripts/docker/*.sh`, level 1's actual opening flyby, `watch_camera.py` extended with `Q`/
`origin_x`/`origin_y`/`screen_w`/`screen_h`/`rb_2a`/`rb_2c` fields):

```text
turn   K       Q        rb_2c   note
 79    46000   40786    16      idle (pre-flyby)
130    9       39251    16      deep-dive plateau (matches "-55.37 deg", "Pitch is not fixed..." above)
343    56140   71207    103     shallow-pitch plateau (matches "-12.70 deg" zoom=80, "zoom_to_pitch calibrated" above)
375    52946   61624    75      easing back down (zoom=0 keyframe engaging)
```

`Q` and `rb_2c` move in lockstep with `K` (same preset-blend fraction driving all three, by construction) and
land at their extremes at EXACTLY the same turns this session's own pitch calibration already pinned down for
`K`/pitch (turn~130-136 dive bottom, turn~340-352 shallow plateau) - strong internal cross-check, not a
coincidence. At the shallow-pitch extreme (`Q=71207`): `focal = 71207*2^-5 = 2225 px` -> `FOV_y=2*atan(240/2225)
=12.3 deg`, `FOV_x=2*atan(320/2225)=16.3 deg` - noticeably NARROWER than idle (21.3/28.2 deg). At the deep-dive
extreme (`Q=39251`, barely below idle's 40786): `focal=1227 px` -> `FOV_y=21.6 deg`, `FOV_x=28.6 deg` - almost
unchanged from idle. **Same out/in asymmetry already documented for the raw zoom accumulator and for pitch
itself** (zooming "in" moves things a lot more than zooming "out" does) - a third independent quantity showing
the identical lopsided curve shape.

**Conclusion**: the original's "zoom" is not just a pitch+bend(K) orbit at a fixed FOV - it's a coordinated
FOUR-way blend (pitch via the matrix, K/bend, Q/focal-length, and a vertical recenter via `origin_y`'s
`render_block+0x2c` term), all driven by the same single preset-interpolation fraction. "Zooming in" in the
original behaves like an actual camera zoom lens (narrower FOV) stacked on top of the pitch swing, not merely a
pitch change - this is the real mechanism behind the "looks like a closer/more telephoto shot" impression a
screenshot comparison would pick up on, more than distance ever could (distance is still provably constant,
confirmed twice over, see "Distance vs. FOV" above).

**Practical fix for `open-populous`**: `flyby.rs`'s `zoom_to_pitch` needs a sibling `zoom_to_fov` (or fold both
into one function returning `(pitch, fov)`), using this session's real calibration points - `(zoom, Q)` pairs:
`(-100, ~39251) (10, ~40786-ish, untested directly) (80, 71207) (0, ~40786 idle)` - `focal_px = Q/32` at `S=11`,
`FOV = 2*atan(half_screen_px / focal_px)`, screen half-dims whatever `open-populous`'s own renderer uses (not
necessarily 640x480 - that's just this capture's fixed window size, not a game-wide constant). **Not yet
checked**: whether MANUAL zoom (not just the flyby) also moves `Q`/`render_block+0x2c` the same way - "Manual
zoom is a pitch+bend orbit" above only ever recorded `D`/`S`/`K`/the matrix, not `Q`, so that section's own
"never a distance dolly" conclusion still stands but its "pitch+bend orbit" framing may be similarly incomplete
for manual zoom too - worth a repeat of that live test with `Q`/`rb_2c` added to the field list now that
`watch_camera.py` has them.

## Flyby cancel - RESOLVED: cancel fast-forwards to the flyby's own end state, not back to the start
Live re-test, this session (headless Docker/Xvfb, `scripts/docker/*.sh`, level 1, hands off the
keyboard after the Space press - `cam9.txt`): cancelled cleanly mid-dive this time (Space sent at
turn ~157-158, `K=9` i.e. deep in the dive, matrix mid-rotation - unlike the earlier `cam3.txt` test
which happened to cancel much later, near-idle-ish `K` values, which is why that capture looked like
a hard one-tick snap). With a real mid-dive starting point the recovery is clearly visible as a
**smooth, monotonic ease, not a snap**: `K` climbs `9 -> 253 -> 832 -> ... -> 46000` and the matrix's
pitch component (`m4`) climbs `9310 -> ... -> 15357` in lockstep, both reaching their exact
idle-default values (`K=46000`, `m4=15357` - "Manual zoom" table above) at the same turn (~195),
**~37 turns / ~3.0 real seconds after the Space press**. `D`/`S` never moved (6500/11 throughout,
confirming "never a distance dolly" holds for cancel too).

**The key new finding is the yaw it eases to.** The settled matrix is `m0=-4853 m2=15648 m3=-5452
m4=15357 m5=-1691 m6=-14668 m7=-5708 m8=-4548`, decoding (`atan2(m2,m0)`) to yaw **~107.2 deg**.
That is, within half a degree, **the exact same yaw** (`~107.8 deg`) that "The intro message dialog
pauses..." above already measured for a flyby left to run to its own **natural**, uncancelled
completion (a completely separate capture, `cam6.txt`, cancelled nowhere, different session). Two
independent captures - one let the script finish on its own, one Space-cancelled it mid-dive at a
totally different turn - converge on the same final orientation. The only sane reading: **Space
doesn't abort the flyby back to some neutral/idle view or the pre-flyby start orientation (the
315-degree idle-hold yaw documented elsewhere in this file) - it skips the rest of the scripted
camera path straight to the flyby's own scripted end keyframe**, then the same
accel/decel/eases-toward-idle-pitch tail plays out either way (cancelled or not). Functionally,
Space-cancel behaves like "jump to the end of this flyby," not "undo/return home."

**Still not captured**: the real focus position (`tribe_struct+0x24`) through a cancel - this test
used the plain `FIELDS` mode (reliable, matches `cam3.txt`'s proven method) rather than
`--scan-tribe` (which hung mid-capture earlier this session, cause not diagnosed - a blocked
`mem.read()` inside the container, possibly worth revisiting before relying on `--scan-tribe` for a
long unattended capture again). `cam_x`/`cam_z` are the known-dead debug fields (see "Ruled out"
above), so position parity between a cancelled and natural-completion run is still open, though given
the orientation result above it would be surprising if position didn't follow the same "skip to the
end" rule.

## `0x4e6a70` traced - not the flyby interpolator (dead end for timing)
`0x4e6a70` (`docs/functions.tsv`, Ghidra's own name `move_pos_angle_length`) is a generic
move-by-polar-vector primitive (`pos += (sin(angle), sin(angle+quarter-circle))·length`, ~100+
call sites exe-wide for units/spells/buildings), not a camera-specific function. Its only camera
callers are `0x442880`/`0x442920` (own rows, mouse-drag pan - see next section), reached from
`FUN_004adbb0`'s MOUSE-DRAG handling (manual player panning), driven by raw per-frame cursor
delta, with no duration/time-progress argument anywhere in the chain. This rules it out as the
scripted flyby's `POS`/`ZOOM`/`ANGLE` channel interpolator - that still-unfound function must take
an explicit time/progress input (consistent with the `+0x30` "interpolation progress" candidate
below being driven from elsewhere). Don't re-trace `0x4e6a70` itself looking for flyby timing;
look instead for whatever reads tribe_struct `+0x30`/`+0x34` or the AI script's own
duration/start-turn values.

## Mouse-drag camera: strafe/dolly/rotate decomposition, no fixed angle or length default
Traced the three sibling functions `docs/functions.tsv` calls them from (`FUN_004adbb0`'s
mouse-drag handling): **`0x442880`/`cam_pan_strafe`, `0x442920`/`cam_pan_dolly`,
`0x4429c0`/`rotate_main_cam`** (Ghidra's own name on the third one, which independently confirms
this whole cluster is camera code). Correction to an earlier session's row: `0x4429c0` does **not**
call `0x4e6a70` - it's a different operation (see below).

- **Neither angle nor length has a fixed/hardcoded default - both are always derived live:**
  - *Angle*: always read from `tribe_base+0x32`, now confirmed as the camera's own stored YAW
    (`0x4429c0` proves it - it adds a delta straight into this field and wraps it mod 0x800/2048,
    i.e. it treats it as a rotation angle). `0x442880` (strafe) uses `yaw - 0x200` (-90 degrees);
    `0x442920` (dolly) uses `yaw` unchanged. So "the angle" is never a constant - it's always
    whatever the camera currently faces, decomposed into forward and perpendicular components.
  - *Length*: the per-frame mouse-cursor delta (`*12`, from `FUN_004adbb0`), optionally rescaled
    by a Q8 fixed-point factor at `0x89c6a9`, gated by flag bit `0x89c66b`&0x10 (=bit 0x100000 of
    the dword at `0x89c669`). That factor's own "default"/identity case is **not scaling at
    all**: `0x4b36b0`/`set_cam_pan_scale` (own row) treats value `0`or `0x100` (Q8 1.0) as "turn
    scaling off", clearing the gate flag so the raw delta passes through unscaled. The one place
    this session found the factor force-set to something else is `0x4b2700` (own row, a larger,
    mostly-untraced scene/mode-transition routine), which hardcodes it to `0x30` (48, ~0.1875x -
    a deliberately slowed pan) while also snapshotting the live camera focus/yaw into a scratch
    struct - looks like entering some special camera mode, not identified yet.
- **Forward/strafe decomposition**: `0x442880` (X mouse-axis) and `0x442920` (Y mouse-axis) both
  call `0x4e6a70(tribe_base+0x24, angle, scaled_delta)`, which does `+=`, so the two accumulate
  into the same focus field - classic "forward along yaw" + "sideways along yaw-90" movement
  composition, not two independent "polar vector" calls with arbitrary angles.
- **`0x4429c0`/`rotate_main_cam` is the actual rotation update**, not a position move: same
  tribe_base/Q8-scale prologue, but it adds the scaled delta directly onto `tribe_base+0x32`
  (yaw) and writes it back, masked to the 2048-unit circle. It also sets a render-dirty bit
  (`0x87ca1c` bit 0x80). Called from `FUN_004adbb0`'s drag-START transition (mode 2), not the
  per-axis ongoing-drag calls.
- **A 3rd, likely-inertia lead opened by this trace**: all three functions mirror their scaled
  delta into one of 3 adjacent global words - `0x8926c7` (rotate), `0x8926c9` (dolly), `0x8926cb`
  (strafe) - which `FUN_004424b0` (own row, not traced in depth) decays/clamps every frame with
  literal constants `0x20`/`0x600`/`0x180`. Plausibly the "camera keeps coasting briefly after you
  release the drag" momentum system. Worth a dedicated session if that's ever user-visible enough
  to matter for `flyby.rs`/manual-pan parity; not pursued further here.

## Camera zoom presets resolved: what advances `vconfig_index`/`vconfig_index_start` (open-populous TODO.md's "VCONFIG0.DAT" question, CLOSED)
`open-populous3`'s own `TODO.md` (`zoom_to_pitch`/`flyby.rs` notes) flags this investigation's earlier discovery of
the real preset data source (`vconfig_dat_mem`, `backup.xml`'s own name for the table at `0x88F0C0` this file
already uses as "the table at 0x88F0C0" throughout - see "The real AI-script zoom chain" above) as needing one more
thing before the 80-100 zoom numbers can be read off directly: "what advances the 'current preset' index during a
real zoom/flyby." Fully resolved this session, **entirely by static tracing** (`dis.txt` + `backup.xml`'s own
`vconfig_struct`/`vconfig_index`/`vconfig_index_start`/`get_vconfig_index` names, cross-checked against each other)
- no live capture needed, confirming the TODO.md note's own expectation.

**The table and its indexing, confirmed exactly via `backup.xml`'s own struct/symbol names:**
`vconfig_dat_mem` (`0x88F0C0`) is `vconfig_struct[50]` (struct size `0x5e`=94 bytes, confirmed matching every
`rep movs ecx=0x17` + trailing word copy this investigation has already traced through it). It is addressed as a
**2D array, not a flat list**: `byte_offset = (vconfig_index*5 + vconfig_index_start) * 94`, where `vconfig_index`
(`0x89C6EE`, 0-9 - "ROW") and `vconfig_index_start` (`0x89C6EC`, 0-4 - "COLUMN/sub-level") are TWO SEPARATE globals
this file previously treated as one ("indexed by 0x89C6EE/0x89C6EF" in the old `0x417510`/`0x41C700` notes above -
`0x89C6EF` was never actually a second index, just the next byte of `0x89C6EE`'s own 2-byte-aligned read). This
exact formula is used consistently by `update_vfconfig`/`0x417338` (the function that actually snaps the live
render block, `0x88F004`, to the current combined preset) and by `0x417510`'s own multi-frame blend target lookup.

**`vconfig_index` (the ROW, "which built-in resolution profile") is NOT a zoom dimension at all - it tracks the
live window/screen resolution, continuously, and nothing a player does to "zoom" touches it.** `get_vconfig_index`
(`0x4171F0`, Ghidra's own name) takes `(width, height)` and returns whichever of the table's 10 rows has the
closest-matching own tag (`vconfig_struct+0x30`/`+0x32`, `backup.xml`'s own member names are literally `width`/
`height` - independent confirmation): an exact match short-circuits immediately, otherwise it minimises a
squared-difference-style metric across all 10 rows. Its 4 callers all pass the CURRENT viewport pixel size
(**correction, a later session**: `0x89C6CF`=width, `0x89C6D1`=height - this session had it backwards; re-confirmed
two independent ways: `cmp WORD PTR 0x89c6cf,0x280` paired with `cmp WORD PTR 0x89c6d1,0x1e0` right next to it at
`0x410e84`/`0x410e8f` - a joint "is the mode exactly 640x480" check, `0x280`=640 against `0x89c6cf` and `0x1e0`=480
against `0x89c6d1` - and `get_vconfig_index`'s own call site at `0x42abc9` pushes `0x89c6cf` as arg1/`width` (checked
against the table's own `+0x30`/"width" field) and `0x89c6d1` as arg2/`height` (`+0x32`/"height"). Matters for the
screen-origin trace below, which depends on getting this pairing right. Compared against literal VGA/SVGA
constants like 640x480/800x600 dozens of times elsewhere in `dis.txt`): `init_all` (once with the hardcoded
640x480 startup default, once with the live resolution), **`draw_main`, every single frame**, and
`reload_hspr_sprites` (after a sprite-bank/resolution-change reload). So `vconfig_index` just continuously re-snaps
to "whichever built-in profile best matches the window's current pixel size" - normally constant during a play
session (the window doesn't resize), never advanced by zoom input or by the flyby.

**`vconfig_index_start` (the COLUMN, 0-4) IS the real, player-facing "camera zoom preset" control - set directly,
never incrementally, by exactly 4 raw UI commands.** `process_cmd`'s own switch (`switchD_004abc0e`, `backup.xml`'s
own `caseD_26`/`caseD_27`/`caseD_28`/`caseD_29` all sharing one target, `0x4abcc0`) computes
`bl = ui_cmd_id - 0x26` (giving literal 0/1/2/3) and calls the shared `0x479F00` dispatcher (`functions.tsv`'s own
row, previously catalogued only as a "banner/message hub" - this session traced its until-now-unread category 0xC)
with `(0xC, bl, 0)`. Category 0xC's handler (`0x47a40f`) saves the OLD value to `0x89C6EB`, writes the new value
into `vconfig_index_start` (clamped/wrapped to 0-4), computes a frame-rate-scaled transition length
(`0x4174B0`, 8-32 frames) into the blend-step counter `0x89CE34`, and snapshots the CURRENT live render block into
a "from" buffer (`0x88F062`) - exactly the setup `0x417510`'s own per-frame multi-frame ease (already traced above,
"Camera-PRESET multi-frame blend") then consumes every frame via `cur += (target-cur)/(steps_left-1)` until it
reaches the new preset. **This is a direct "jump to preset N" command, not a relative +/- step** - there is no
code path anywhere that increments/decrements `vconfig_index_start` by one; each of the 4 raw ids IS one specific
target value. Exhaustively grepped every "call 0x479f00" site in `dis.txt` (~100 call sites) confirms these 4 are
the ONLY callers of category 0xC anywhere in the exe. The physical keybind/menu button for `ui_cmd 0x26-0x29`
wasn't identified this session (not found under this name in `open-populous3`'s own `docs/specs/shortcuts.md`;
that doc's own "+/- zoom" entries correspond to the CONFIRMED-DEAD debug pan/zoom key handlers this file's own
"Ruled out" list already flags, a different, unrelated global, `0x89C6C3`/`0x417270`, not `vconfig_index_start` -
see `functions.tsv`'s `0x417270` row, added this session, for that disambiguation).

**The flyby's own live zoom channel (`tribe_struct+0x34`, "The real AI-script zoom chain" above) never writes
EITHER index - it only reads `vconfig_index` (the row) to pick two FIXED neighbours within that row to blend
between, ignoring whatever `vconfig_index_start` currently is.** Re-reading `0x41C700`/`preset_blend_by_fraction`'s
index arithmetic in full this session (an earlier pass through this investigation missed one extra `*5` term)
shows presetA is ALWAYS `vconfig_dat_mem[vconfig_index].sub[0]` and presetB is ALWAYS
`vconfig_dat_mem[vconfig_index].sub[2 or 3]` (2 for zoom-out/positive `signed_delta`, 3 for zoom-in) - a hardcoded
sub0-to-sub(2|3) blend within whichever row the live screen resolution currently matches, completely independent
of the live `vconfig_index_start` value a player's own zoom-preset command might have set. So during a flyby, the
ZOOM channel and a player's own manual zoom-preset keys (if pressed at the same time) don't interact or conflict -
they drive genuinely separate preset slots of the same table. `functions.tsv`'s `0x41C700` row has the full
corrected index derivation.

**A 5th code path, confirmed DEAD, would have let something set `vconfig_index` (the row) directly with wraparound
- never reachable from anywhere.** `0x479F00` category 0xE (`0x47a4e4`) does `vconfig_index = bl`, wrapped mod-10
(`<0 -> 9`, `>9 -> 0`) - looks exactly like a generic "advance the zoom row with wraparound" primitive, but
exhaustively grepping every "call 0x479f00" site in `dis.txt` found NONE passing `arg1=0xE` (14) - this branch is
unreachable code in this build. Worth knowing if a different game version/patch ever turns out to wire a caller to
it, but in this build `vconfig_index` is never advanced by anything resembling a zoom command, direct or
incremental - only by the per-frame resolution re-match described above.

**Net answer to "what advances the current preset index during a real zoom or flyby,"** fully resolved, no live
memory needed: **nothing "advances" either index by a delta; both are always SET outright.** `vconfig_index` (the
resolution row) is continuously reset every frame from the live window size, never touched by zoom/flyby logic at
all. `vconfig_index_start` (the actual zoom-preset dimension a player can change) is set directly to one of 4
literal values (0-3) by 4 dedicated raw UI commands (`ui_cmd 0x26-0x29`, `docs/commands.tsv`'s own new rows), each
triggering a smooth multi-frame ease to the new preset; there is no continuous/relative zoom-stepper command for
it anywhere in this build. The AI-script flyby's own zoom channel is a third, independent mechanism again (already
fully traced above) that blends within fixed sub-slots 0/2/3 of the row, untouched by and not touching either
index. **Practical implication for `open-populous`'s `flyby.rs`/`zoom_to_pitch`**: the "80-100 zoom" extrapolation
TODO.md flags doesn't need `vconfig_index_start` tracing after all - the flyby's own `ZOOM` channel (script values
-100..100) only ever reaches sub-presets 0/2/3 of whatever row the current resolution matches, a closed, already-
enumerable set (10 rows * 3 relevant sub-slots = 30 `vconfig_struct` records total) rather than all 50 - reading
those presets' own `K`/`D`-adjacent fields directly (once `vconfig_dat_mem`'s on-disk/in-memory layout is dumped,
a static read, no live capture) would settle the pitch-at-extreme-zoom question exactly instead of extrapolating.

## Screen origin (`origin_x`/`origin_y`) asymmetry SOLVED: the ~50px X offset is a real, deliberate UI-panel inset, not a bug or a bad measurement
`open-populous3`'s own `TODO.md`/`pop3-rev-analysis.md` "Landscape projection" flags an open item from the per-axis
screen-scale trace: `origin_x`/`origin_y` (screen center, added after the `focal_px·x'/z'` perspective divide) were
found as `render_block[+0x2a or +0x2c] + screen_width_or_height/2`, live-confirmed exact for Y but off by a
constant ~50px for X "for a reason not yet found." Fully resolved this session, **entirely by static tracing**
(`dis.txt` only, no live memory needed) - and the root cause is a genuine, intentional asymmetry in the code, not a
mismeasurement or a mislabeled axis.

**The exact formula**, read straight out of `coord_pnts_global_convert`/`0x46DE00` (Ghidra's own name,
`backup.xml`'s `SYMBOL` entry - confirms the identity `pop3-rev-analysis.md`/`TODO.md` already used for this
address; `functions.tsv`'s own row for it had the formula but not the name, now fixed) and its near-duplicate
`0x46DC40`:

```text
origin_x = render_block[+0x2a] + render_block[+0x26] / 2
origin_y = render_block[+0x2c] + render_block[+0x28] / 2
```

confirming the TODO.md note's own guessed shape exactly (word-sized fields throughout, standard arithmetic shift
for the `/2`). The asymmetry isn't in this formula - both axes are structurally identical here. It's in what feeds
`render_block[+0x26]` vs `[+0x28]` (the "half-dimension" terms): traced to `FUN_00417270`/`0x417270` (own
`functions.tsv` row, previously catalogued this session's history as "a map/minimap scroll-row-and-column
viewport" - that read was a plausible guess from the write targets alone, now corrected with the actual data-flow
traced):

```text
reserved_px = 0x44BB80()                         # 0 if the UI side panel is hidden, else a pixel width (below)
margin = si                                      # the fn's own byte argument, always called with si = global 0x89C6C3

render_block[+0x22] = reserved_px + margin*8     # clip-rect LEFT  (copied onward to 0x87CA8C, "Landscape projection")
render_block[+0x24] = margin*8                   # clip-rect TOP   (copied onward to 0x87CA8E)
render_block[+0x26] = SCREEN_WIDTH  - reserved_px - margin*16   # <- origin_x's own half-dimension term
render_block[+0x28] = SCREEN_HEIGHT               - margin*16   # <- origin_y's own half-dimension term
```

(`SCREEN_WIDTH`/`SCREEN_HEIGHT` here are `0x89C6CF`/`0x89C6D1` respectively - see the correction just above this
section; getting this pairing right was what made the formula fall into place, after an earlier pass through this
same instruction sequence briefly read it backwards.) **`render_block[+0x26]` (the X half-dimension) has
`reserved_px` subtracted; `render_block[+0x28]` (the Y half-dimension) does NOT** - the entire asymmetry comes from
this one term being X-only. Since `origin_x` ends up `(SCREEN_WIDTH - reserved_px - margin*16)/2` instead of the
naive `SCREEN_WIDTH/2`, it reads low by `reserved_px/2` (the `margin` term affects both axes equally via the
`*16`/`*2`, so it cancels out of the X-vs-Y *difference* - it's not the source of the asymmetry, `reserved_px` is).

**`reserved_px` is the game's UI side panel's own pixel width - confirmed by the flag that gates it.**
`0x44BB80` (own new `functions.tsv` row) returns `0` outright if global `0x89C661` bit `0x4` is set, else either a
flat fallback of `128` (if a per-resolution lookup table at `0x684220` has no matching row) or
`table_entry * SCREEN_WIDTH / 65536` (a resolution-proportional fraction, Q16, from whichever row a key at
`0x68C6C5` selects) - i.e. a pixel width that scales with the window, exactly how a HUD panel's width would be
expressed. `0x89C661` bit `0x4` is independently confirmed to mean "the UI panel is hidden": every caller of
`0x417270` sets/clears/toggles this exact bit immediately before calling it (`0x42B4CA`, `0x458105`/`0x4580FE`,
`0x47A3A2`/`0x47A392`/`0x47A39B` - the last three live inside `0x479F00`'s own dispatcher, gated on a 3-way
positive/negative/zero argument that reads exactly like a show/hide/toggle UI command), and `0x44BB80` is the ONLY
reader of that bit anywhere that also touches a per-resolution pixel-width table. So: **with the panel visible
(the normal play state, and presumably the state during whatever live measurement produced the original "~50px"
figure), `origin_x` is centered on a viewport that's narrower than the full screen by the panel's own width,
because the panel occupies screen space on one side only (horizontally) - nothing analogous ever reduces
`SCREEN_HEIGHT` for `origin_y`, because the panel doesn't eat into vertical space.** This is the concrete,
code-grounded answer to all three of the task's candidate explanations: it's not a FOV/aspect correction and not a
general screen-centering offset (those would move both axes, or scale with aspect ratio, not drop a fixed amount
from X alone) - it is, literally, **UI-sidebar-width compensation**, baked into the one place (`[+0x26]`) that
feeds the horizontal half-dimension and nowhere else.

**What a live check would need to pin the exact "~50px" figure, if ever wanted precisely** (not required for the
mechanism above, which is fully static): `0x44BB80` caches its own return value at `0x59CD7C` every call - a
single live read of that global gives `reserved_px` directly, no need to re-derive the table lookup. Divide by 2
(for the "/2" in the origin formula) and that should equal the originally-measured X-vs-naive-half-width gap
exactly, for whatever resolution/panel-visibility state that measurement was taken at. The `margin` term (global
`0x89C6C3`, 0-32 range, set by other `0x479F00` UI commands, unrelated to the already-ruled-out dead debug
pan/zoom keys despite superficially similar code shape - `functions.tsv`'s `0x417270` row has the disambiguation)
affects both `[+0x26]` and `[+0x28]` identically and so doesn't change the X-vs-Y gap, but would need to be read
too if reproducing the absolute `origin_x`/`origin_y` values rather than just their difference.

**Not pursued further this session, smaller remaining threads**: `render_block[+0x2a]`/`[+0x2c]` (the additive
terms ahead of the halved dimensions, both default to a small constant - `0`/`0x10` respectively, from the
render-block-defaults function `0x416F50`, own row expanded this session with the full default dump) are
themselves eased every frame toward a camera-preset's own `+0x2a`/`+0x2c` fields by the same multi-frame blend
function already traced for `K`/`D`/etc (`0x417510`, "Camera-PRESET multi-frame blend" above) - so in principle a
*second*, independent source of X-vs-Y difference could live inside the `vconfig_struct` preset table's own data
(if a preset's `+0x2a` and `+0x2c` aren't both zero). Not read this session (would need the live/on-disk
`vconfig_dat_mem` dump already flagged as a useful follow-up above); the panel-width mechanism above is already a
complete, sufficient, confirmed explanation for an asymmetry that's X-specific and roughly constant, so this is a
secondary lead, not a gap in the main finding.

## Open questions / next steps
1. ~~Pin `FLYBY_START`'s turn exactly~~ **SOLVED** this session: **turn 72**, read straight from the compiled
   script's own `Every{period:8} / IF INT_GAME_TURN>70 / IF $57==0` gate via the `ai_script_info` example
   tool - see "FLYBY_START's turn - SOLVED EXACTLY" above. No live memory needed.
2. ~~Solve `+0x28`'s raw-to-pitch-degrees transform~~ **STRENGTHENED DEAD END**, a later session: a
   same-capture regression against the matrix's own `M21` (`cam7.txt`) gets R²=0.395 at best, lag
   search included - confirmed NOT a memoryless function (even lagged) of current pitch, with a
   decisive counter-example pair. See "`+0x28` is not a function of current pitch" above. Next step,
   if ever revisited: stop regressing against `M21` and instead look for what else could be driving
   it (hysteresis/accumulator state, or an unrelated field at the same shared offset).
3. ~~Decode the `POS` waypoints' own coordinate units~~ **SOLVED** this session: plain 0-255 cell indices,
   world units = `(cell+1)*256` - see "POS and ANGLE channels" above.
4. **RESOLVED**, a later session (live re-test, `cam9.txt`): Space-cancel is not an abort-to-idle -
   `K`/pitch eases smoothly (~3s) to the idle default, and the matrix's yaw converges to the exact
   same end orientation (~107.2-107.8 deg) that an uncancelled flyby reaches on its own - cancel
   skips to the flyby's own scripted end state rather than returning to the start. See "Flyby
   cancel" above. Only the real focus position (`+0x24`) through a cancel remains unverified.
5. ~~Apply the D3D axis caveat to yaw~~ **SOLVED for the `ANGLE` channel**, a later session, using the
   user's own `yaw_true = s*raw*360/2048 + c` model against `cam5.txt`/`cam7.txt`'s per-turn data (exactly
   the "check this properly" follow-up this item used to ask for): `s=-1, c=0` (pure sign flip, the
   left-handed/right-handed mirror `open-populous`'s own `GameYaw::render()` already applies) fits four
   independent keyframes to within ~0.5-4 deg in BOTH captures; `s=+1` is off by 100-150 deg on every
   non-trivial point - see "D3D axis caveat for YAW - RESOLVED" above. `open-populous`'s `flyby.rs` needs
   no change for yaw's scale/sign, it already calls the mirrored conversion. Position's own axis handling
   was separately resolved too (it's a scale bug, not a handedness one - "Correction: POS/TOOLTIP/
   end-target..." above). Pitch's sign was already corrected earlier ("Landscape projection").
6. ~~What actually writes `tribe_struct+0x2c`~~ **SOLVED/CLOSED, a later session**: it isn't a real
   field - `--scan-tribe`'s "+0x2c dword" is an aliasing artifact of two adjacent, independently-written
   fields (`+0x2a` dword and `+0x2e` word), both straight per-frame copies of already-tracked render-block
   fields, made by a newly-found function (`set_player_transform_matrix`/`0x47F480`) called from
   `update_vfconfig`. Found via a live GDB hardware watchpoint (`scripts/watch_addr.py`, new generic tool).
   See "`tribe_struct+0x2c` solved" above for the full mechanism - lead (b) from the old list here turned out
   to be exactly right, just not about `D`. With `FLYBY_START` now exact, a fresh capture would still let the
   `ZOOM`/`POS`/`ANGLE` channels' own scale/offset (still only "right shape" R²~0.1-0.6, "Joint fit" above) be
   fit properly against clean, correctly-aligned turn numbers instead of a grid search over the start turn too.
7. ~~Trace `0x44A070`~~ **MOSTLY SOLVED**, a later session: it's a generic kinematic ease-setup shared by
   every flyby channel's `start` callback (ZOOM/POS/ANGLE/INT_POINT all call it) - see "The `0x44A070`
   ease-setup helper" below. The outer shape (duration scaling, stopping-distance branch, one-phase vs.
   two-phase cases) is confirmed from static disassembly alone, no live memory needed; the exact algebra of
   the two-phase branch's blend (past where it splits the duration into a "kill existing rate" piece and a
   remainder) wasn't fully re-derived - a further session could finish that if the precise acceleration curve
   ever matters for `flyby.rs` (it's plausibly within smoothstep/easing error tolerance already).
8. ~~What advances the "current preset" index (`vconfig_index`/`vconfig_index_start`) during a real zoom or
   flyby~~ **SOLVED**, a later session, entirely statically (no live capture, confirming `open-populous`
   `TODO.md`'s own expectation): neither index is ever incremented - `vconfig_index` (the resolution-ROW) is
   reset every frame from the live window size via `get_vconfig_index`/`0x4171F0`, untouched by any zoom/flyby
   logic; `vconfig_index_start` (the real zoom-preset dimension) is SET directly (never stepped) to one of 4
   literal values by 4 dedicated raw UI commands (`ui_cmd 0x26-0x29`, `docs/commands.tsv`); the flyby's own zoom
   channel (`0x41C700`) reads `vconfig_index` only, to blend within two fixed sub-slots of that row, and touches
   neither index. See "Camera zoom presets resolved" above for the full derivation. **This also resolves item 13
   below's own "genuine open contradiction" from a parallel investigation thread that reached this same question
   from the other direction** (via `0x89C6EE`/`vconfig_index` itself, not `vconfig_index_start`): that thread's
   four found writers of `0x89C6EE` (`0x42ABE1`/`reload_hspr_sprites`, `0x4A49DE`/`draw_main`,
   `0x4A5086`/`0x4A51F5`/`init_all`) are exactly the same resolution-row-reset call sites this item's own
   derivation already accounts for - `0x89C6EE` was never the zoom control to begin with, so there is no
   contradiction left to explain once `vconfig_index_start` (a different global, `0x89C6EC`) is recognised as the
   real zoom dimension.
9. ~~Why does `origin_x` carry a constant ~50px offset `origin_y` doesn't~~ **SOLVED**, a later session, entirely
   statically: `origin_x`'s own half-dimension term (`render_block+0x26`) has the UI side panel's live pixel width
   subtracted before halving; `origin_y`'s (`render_block+0x28`) does not, because the panel only occupies
   horizontal screen space. A real, deliberate asymmetry, not a bug or a bad measurement. See "Screen origin
   (origin_x/origin_y) asymmetry SOLVED" above for the full derivation and what a live check would still need to
   pin the exact pixel figure.

**Items 10-13 below are from a separate, parallel investigation thread that worked through this same backlog
independently (merged in from `origin/main`) - its own item numbers 8-11 collided with the two items just above
and have been renumbered 10-13 to fit after them; nothing in its own text was otherwise changed.**

10. ~~Check the POS channel's raw-byte-to-cell scale against `open-populous`'s own 128-cell map~~ **SOLVED**,
   found via a user's screenshot comparison rather than new live memory: raw x/z are HALF-cell units
   (`actual cell = raw / 2`), not literal cell indices - see "Correction: POS/TOOLTIP/end-target raw x/z are
   HALF-cell units" above. Also connects the already-known "zoom=0 is neutral" finding to `flyby.rs`'s own
   pitch mapping - see "Correction: flyby zoom value 0 means 'idle'" above. Yaw's own offset/sign convention
   (open question 5's D3D axis caveat) was the one item left over from that same comparison - now also
   **SOLVED**, see item 5 above and the next item.
11. ~~Calibrate `ANGLE`'s yaw sign/scale and `ZOOM`'s pitch curve for real, with >=2 ground-truth points each~~
   **SOLVED, a later session, from data already on hand**: re-ran the same flat-hold-detection pipeline (built
   for the yaw check, item 5) against `cam5.txt`/`cam7.txt`'s matrix pitch instead of yaw, matched to level 1's
   4 `ZOOM` keyframes - see "`flyby.rs::zoom_to_pitch` calibrated against the same traces" above. Confirms
   zoom=0 -> idle pitch exactly, AND finds the bigger issue: the script's own -100..100 domain only reaches
   -55.4 deg to -12.7 deg for this level, nowhere near `PITCH_RANGE`'s manual-zoom-derived 10.5-88.6 deg span -
   `zoom_to_pitch` was fit against the wrong input's range entirely. `D` (distance) remains untestable from
   these traces (wrong struct) but was already settled two other ways (live round-trip test + static chain
   trace) - zoom never touches it, scripted or manual.
12. Derive `S`'s real equivalent FOV for the "Distance vs. FOV" question (above). **SOLVED, a later session**:
    whether level 1's own flyby touches the OTHER, untraced camera-distance mechanism (`0x417510`, blends `D`/
    `S`) was checked and RULED OUT (level 1's actual `cpscr010.dat`, parsed via `ai_script_info`, uses none of
    `ZOOM_TO`/`TRACK_SHAMAN_TO_ANGLE`/`TRACK_TO_MARKER`/`CREATE_MSG_INFORMATION_ZOOM`/other `SET_MSG_*ZOOM*`
    opcodes, only the one known `Flyby`). The per-axis screen scale itself is now fully traced from pure static
    disassembly, no live capture needed for the formula (`0x46de00`'s tail end + its `0x5215b3`-ish setup
    function) - see "The per-axis screen scale SOLVED" above: it's isotropic (the per-axis split algebraically
    cancels), `focal_px = Q * 2^(S-16)` where `Q = tribe_struct+0x2a` (a DIFFERENT field from this same offset's
    other use as a camera-focus-adjacent dword in the POS correction above - confirmed via live reads matching
    the static default exactly, `Q=40786` idle). **Bigger finding from the same session, live-confirmed**: `Q`
    is itself one of the flyby `ZOOM` channel's 5 blended fields, swinging from ~39251 (deep dive) to ~71207
    (shallow "zoomed in" extreme) - "zoom" changes effective FOV (12.3-28.6 deg observed range) on top of pitch,
    not just a pitch+bend orbit at fixed FOV. See "Zoom changes effective FOV too" above. Still open: the
    `origin_x` discrepancy (predicted 320, observed 270, constant offset, cause unfound), what `0x417510`'s real
    trigger is (not level 1), whether MANUAL zoom also moves `Q`/`render_block+0x2c` the same way (untested),
    and `render_block+0x20`/`+0x2e` (the 2 still-unnamed fields of the same 5-field zoom blend).
13. **The preset TABLE itself, found and decoded from pure static data - no live memory needed for the numbers.**
    **Note added when merging this thread back in: the "current index must itself advance past 0" puzzle and the
    Q-mismatch "genuine open contradiction" raised a few paragraphs below are both resolved by item 8 above,
    found independently by a parallel thread - `0x89C6EE` (`vconfig_index`) is only ever the resolution-ROW
    matcher, reset every frame; the real zoom-preset control is a DIFFERENT global, `vconfig_index_start`
    (`0x89C6EC`), set directly by 4 dedicated UI commands (`ui_cmd 0x26-0x29`). The writers of `0x89C6EE` found
    below (`0x42ABE1`, `0x4A49DE`, `0x4A5086`/`0x4A51F5`) are exactly that resolution-row reset, not a second
    zoom mechanism - there was no contradiction left once the two globals are told apart.**
    `preset_blend_by_fraction`'s (`0x41C700`) own table (`0x88F0C0`, 10 presets × 470 bytes, confirmed by the
    indexing arithmetic in that function) is runtime data, but it's loaded verbatim from a real file,
    `data/VCONFIG0.DAT` (4700 bytes = 10 × 470 exactly, confirmed), via `init_vconfig`/`0x4170FA`'s own
    seek+read pair (`0x5001B0`/`0x525F80` against file handle `0x89CD23`) - decoded directly with a small Python
    script (`consts.py`'s own `va2off` doesn't apply, this is an external file, not exe-embedded data). All 10
    presets' known fields (K `+0x0`, Q `+0x8`, `+0x20`/`+0x2c`/`+0x2e`/`+0x34`):

    | preset | K | Q | +0x20 | +0x2c | +0x2e | +0x34 |
    |---|---|---|---|---|---|---|
    | 0 | 46000 | 40786 | 1932 | 16 | 195 | 280 |
    | 1 | 46000 | 35154 | 1932 | -7 | 276 | 280 |
    | 2 | 35248 | 40786 | 1932 | 0 | 335 | 280 |
    | 3 | 35248 | 40786 | 1932 | -77 | 425 | 280 |
    | 4 | 44208 | 35154 | 1900 | 88 | 222 | 280 |
    | 5 | 46000 | 38226 | 1916 | 50 | 150 | 280 |
    | 6 | 46000 | 40786 | 1932 | 16 | 150 | 280 |
    | 7 | 46000 | 29522 | 1932 | 67 | 222 | 280 |
    | 8 | 46000 | 40786 | 1932 | 16 | 222 | 280 |
    | 9 | 46000 | 40786 | 1932 | 16 | 222 | 280 |

    **Preset 0 = idle, confirmed exactly**: Q=40786 and `+0x2c`=16 match the already-live-measured idle values
    (item 10 above) to the digit - strong validation that this decode and the field offsets are both right.
    `preset_blend_by_fraction` always blends FROM the "current preset index" (`0x89C6EE`) TO current+2 (zoom-out,
    positive internal delta) or current+3 (zoom-in, negative/zero internal delta). With current=0 at idle, that's
    preset 2 (out) / preset 3 (in) - but neither has Q far from idle's 40786 (preset 3 is identical to idle on
    every field but `+0x2c`/`+0x2e`), which does NOT match the live-observed Q~71207 at the flyby's own deepest
    "zoomed in" point (item 10). **So "current index" must itself advance past 0 during a real zoom/flyby** (the
    `0x88F061` "both presets at the table's end" dirty flag hints at exactly this kind of chained traversal) -
    not traced this session. **Next step to finally pin script zoom 80-100 (and `flyby.rs`'s whole `*_KNOTS`
    curve) exactly, with no live data needed at all**: find what updates `0x89C6EE` (grep its writers) and under
    what condition, then walk the preset chain the same way the game does for a given cumulative zoom input.
    **Partial answer, same session**: `0x89C6EE`'s only writers are inside one big function (`FUN_00479F00`,
    Ghidra's own typeinfo: `(byte param_1, ushort tribe_num, int param_3)`, `0x479F00`-`0x47A50E`) - its tail
    sets the index directly to a passed-in byte, with CIRCULAR wraparound at the 10-preset boundary (negative
    -> 9, `>9` -> 0), after copying one 94-byte sub-record between two preset slots (the same 94-byte stride
    `init_vconfig_struct_array`'s own row logs). So "current preset" is a direct, caller-chosen jump (likely a
    scripted/UI "switch to camera view N" command, matching the function's own `tribe_num` parameter), not an
    accumulate-by-zoom-amount counter - the smooth `-100..100` feel must come entirely from the fractional blend
    toward `current+2`/`current+3`, with "current" itself only moving on a distinct event, not continuously.
    **This likely resolves the apparent Q mismatch above too, without contradiction**: the live-measured
    Q~71207 "zoomed in" extreme may well have come through the OTHER, separately-flagged preset-blend mechanism
    (`0x417510`, "Camera-PRESET..." - still not fully traced, open question above) rather than through this
    `0x41C700` zoom channel at all, since level 1's own flyby was never checked against `0x417510`'s own trigger
    condition specifically for this capture. **Narrowed further, same session**: `0x479F00` is a much bigger,
    generic multi-purpose dispatcher than "a camera command" - its own `param_1` (1-15) selects between 15
    unrelated case bodies, and checking every one of its ~100 call sites found NONE pushing the literal `14`
    needed to reach the camera-index case (`caseD_d`, `0x47A4E4`) - every literal caller passes 1/5/6/7/8/0xA/
    0xB/0xC/0xD/0xF instead, for whatever `0x479F00`'s OTHER 14 cases do. The few callers that pass `param_1`
    dynamically (a register, not a literal) trace back, at the one checked (`0x4B40BC`), to a settings-style
    dispatch keyed by two other globals (`0x98F666`/`0x98F667`) that reads like an options/menu system, not
    gameplay or AI-script code - plausibly a "camera style" menu option, never touched by ordinary play or a
    level script. **This does NOT actually resolve the Q mismatch - it sharpens it into a real contradiction,
    left open rather than guessed at**: `0x417510` was independently RULED OUT for this exact capture earlier
    in this file ("Distance vs. FOV" above) - level 1's own parsed script (`cpscr010.dat`, checked directly) uses
    none of `CREATE_MSG_INFORMATION_ZOOM`/`ZOOM_TO`/`TRACK_TO_MARKER`/the other `SET_MSG_*ZOOM*` opcodes, only the
    one `Flyby` - and Q~71207 was measured DURING that exact flyby, already attributed to `0x41C700` itself (item
    10 above, "Q is itself one of the flyby ZOOM channel's 5 blended fields"). So the Q~71207 reading demonstrably
    came through `0x41C700`/`0x89C6EE`'s own mechanism, yet no literal caller of `0x479F00` reaches the camera
    case and the one dynamic caller checked looks menu-only - these two findings conflict and are NOT reconciled
    here. Left as a genuine open contradiction rather than resolved either way: either `0x89C6EE` has another,
    unfound writer (a second, non-`0x479F00` path), or "current preset" isn't actually what's moving and the real
    explanation for Q's swing is a DIFFERENT accumulator this session hasn't found. **There IS at least one such
    writer, found but not traced to a conclusion**: `0x42ABE1` (inside `reload_hspr_sprites`, Ghidra's own name -
    plausibly wrong/stale for this call site) writes `0x89C6EE` directly from the return value of `0x4171F0`,
    called with two other globals (`0x89C6CF`/`0x89C6D1`, word) that read like mouse/cursor coordinates (checked
    a few lines later against `0x200`/`0x180`) - NOT traced further this session; `0x4171F0` itself is unread.
    Two more direct writers exist too (`0x4A49DE` in `draw_main`, `0x4A5086`/`0x4A51F5` in `init_all`), neither
    opened. Any of these is a more promising lead than `0x479F00` for what actually drives "current preset"
    during ordinary play - next session should start with `0x4171F0`.

## Raw capture logs
Not committed, scratch only: `cam.txt` (POPTB.EXE, mistranslated address lesson - m1..m8 read stuck
at 0 the whole time due to `addrmap.py`'s anchor+delta fallback being wrong for that struct), `cam2.txt`/
`cam3.txt` (native `D3DPOPTB.EXE`, pre-`--scan-tribe`, trustworthy), `cam4.txt`/`cam5.txt`
(`--scan-tribe` runs, native, trustworthy; `cam5.txt` is the first turn-anchored full-flyby capture).
`cam6.txt` (native `D3DPOPTB.EXE`, fixed field list not `--scan-tribe`; first capture from the
headless Docker/Xvfb setup, see "The intro message dialog pauses..." above).

`cam7.txt` (`--scan-tribe`, headless Docker/Xvfb setup, a later session): the cleanest full-flyby
capture so far - capture was started while the turn-72 intro dialog was already on screen (caught
live via an `import -window root` screenshot of the Xvfb display rather than guessed from timing),
dismissed with one `xdotool key Return`, then left running turn-continuously (turn 81 through 438,
fully settled/idle at the end, no gaps) with no dialog-pause artifact to reason around at all. Covers
the matrix (`+0x00..+0x20`) and every candidate field (`+0x24/0x28/0x2c/0x30/0x34`) in one run, which
is what made the `+0x28`-vs-`M21` regression above possible (earlier captures never had both in the
same file). Also reproduces `cam4.txt`/`cam5.txt`'s `+0x2c` zoom-channel numbers almost exactly
(idle 1932, minimum 1733 at the same turn region, maximum ~1976) - third independent confirmation of
that trajectory, mechanism still unsolved (open question 6).

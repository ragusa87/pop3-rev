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
  former open question "decode the POS waypoints' own coordinate units":** the script's raw x/z values are
  plain **0-255 cell indices** (the queueing code packs each into a single BYTE, which only works if they
  fit in 0-255 - matches the worked example's "252 254" etc. exactly), converted to world/render units via
  `(cell + 1) * 256` (confirms "256 render units per cell", "Landscape projection"). The tick callback eases
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

## Flyby cancel (unresolved)
Space-cancelling mid-flyby (`cam3.txt`) shows a sharp one-step matrix discontinuity at turn 257 right
after a brief hold near 108°, then erratic movement (257-283, likely the user's own arrow-key taps)
before a final hold ~107.8° (284-300, capture end). User reports the camera visibly jumped back
toward the start position right after cancelling, before touching the arrow keys - not yet precisely
correlated against the raw matrix trace. Needs a re-run with Ctrl+C'd exact turn numbers noted by eye
for the cancel press, to cleanly separate script-driven vs. manual segments.

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
4. Re-run the cancel capture with precisely-timed Ctrl+C'd turn numbers (see "Flyby cancel" above).
5. Apply the D3D axis caveat once position/angle values are solid enough to change `flyby.rs`. New
   lead (see "The intro message dialog pauses..." above): a before/after matrix yaw vs. the
   script's final `ANGLE` keyframe lined up ~180° apart in one capture - check this properly
   against `cam5.txt`'s per-turn data.
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

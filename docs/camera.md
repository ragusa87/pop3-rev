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
| `+0x28` hi 16 bits | wraps like a cyclic angle; flat exactly when pitch is flat even while yaw keeps moving (decisive: turns 185-270, yaw moves freely, this field and pitch both sit dead flat for 85 straight turns) | raw pitch angle | shape strongly correlates with pitch; raw-to-degrees transform not solved - tried simple ratios at two sample points, inconsistent (not a constant scale, not a constant offset from `M21`) |
| `+0x28` lo 16 bits | pinned at constant `0x0065` the whole capture | unrelated adjacent byte/flag | - |
| `+0x2c` | smoothly monotonic, always an exact multiple of `0x10000` in both captures | camera distance/zoom | STILL NOT the zoom channel (see "The real AI-script zoom chain" below, traced fully - it never touches this field); correlates with the `ZOOM` channel's timing but by some other, still-unfound mechanism |
| `+0x30` | ramps between 0 and exactly `0x1000000` (2²⁴), direction flips at each transition, holds at the max through idle/hold windows | per-segment interpolation progress, 8.24 fixed point (0.0-1.0) | plausible shape, not cross-checked against a ground-truth progress value |
| `+0x34` | **CONFIRMED** (see "The real AI-script zoom chain" below): the zoom channel's own live, signed Q14 fixed-point accumulator (16384 = 1.0, same scale as the rotation matrix), clamped to [-16384, +16384], written every turn by `0x449B30`'s tick callback and fed straight into `0x41C700` to blend camera-preset render-block fields. The "grows with an almost-constant second difference" shape this table used to describe is consistent with `0x44A070`'s own (not fully traced) per-tick increment scheme. |

**Ruled out** (checked, don't revisit without new evidence): `cam_x`/`cam_z` (`0x89CE49`/`0x89CE45`),
the zoom slider pair (`0x89CE3F`/`0x89CE40`), and the projection's `D`/`S` (`0x87CA64`/`0x87CA68`)
never changed across three captures, including one with real arrow-key pans and zoom-wheel input.
These are `process_cmd`'s debug pan/zoom key handlers (`switchD_004AABCA` caseD_32-3D), not live
camera fields in actual play - a dead/unused code path (same genre as the `ui_cmd 0x6D` mistake in
`docs/commands.tsv`). `K` (bend, `0x87CA5C`) DOES vary live, oscillating during camera transitions,
matching the documented "render block can blend" behaviour.

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
2. Solve `+0x28`'s raw-to-pitch-degrees transform (need more samples; two-point ratio checks didn't
   resolve to a constant).
3. ~~Decode the `POS` waypoints' own coordinate units~~ **SOLVED** this session: plain 0-255 cell indices,
   world units = `(cell+1)*256` - see "POS and ANGLE channels" above.
4. Re-run the cancel capture with precisely-timed Ctrl+C'd turn numbers (see "Flyby cancel" above).
5. Apply the D3D axis caveat once position/angle values are solid enough to change `flyby.rs`.
6. **What actually writes `tribe_struct+0x2c`, still unsolved - the "zoom while a popup is open" theory is
   now RULED OUT too.** All FIVE channels (ZOOM, POS, ANGLE, INT_POINT, TOOLTIP) and the entire tooltip/
   notification pipeline on BOTH the creation side (`0x44D7F0`/`0x44A030`) and the rendering side
   (`render_land_ui_1`/`0x44A34D`) are now confirmed to never touch it, the render-block D field, or the
   `0x89CE34` transition counter - see "INT_POINT and TOOLTIP channels" above. The `TOOLTIP`-timing
   correlation itself still stands (unexplained), but its most plausible mechanism doesn't exist in code.
   Remaining leads, genuinely open: (a) a live hardware write-watchpoint on the computed `tribe_base+0x2c`
   address during a fresh flyby run - static grepping for a combined-immediate access to it found nothing,
   suggesting the access is split across instructions in a way that doesn't show up as a single recognizable
   literal, so a live watch may be faster than more static searching; (b) treat `+0x2c` as a passively-updated
   mirror of the render block's own D (or some other already-tracked value) computed once per frame
   elsewhere, independent of any flyby channel; (c) the correlation could be coincidental - with `FLYBY_START`
   now exact, a fresh `cam*.txt`-style capture would at least let this be checked against a 2nd, independent
   flyby run (different timing noise) rather than the two already-captured ones (which may share a common
   capture-session artifact). With `FLYBY_START` now exact, a fresh capture would also finally let the `ZOOM`/
   `POS`/`ANGLE` channels' own scale/offset (still only "right shape" R²~0.1-0.6, "Joint fit" above) be fit
   properly against clean, correctly-aligned turn numbers instead of a grid search over the start turn too.
7. **`0x44A070`, not traced this session** (`docs/functions.tsv`): the per-tick increment/ease-setup helper
   every channel's `start` callback calls (ZOOM, POS, ANGLE all use it) - tracing it would give the exact
   per-tick stepping formula generalized across all channels, not just the zoom-specific read done this
   session.

## Raw capture logs
Not committed, scratch only: `cam.txt` (POPTB.EXE, mistranslated address lesson - m1..m8 read stuck
at 0 the whole time due to `addrmap.py`'s anchor+delta fallback being wrong for that struct), `cam2.txt`/
`cam3.txt` (native `D3DPOPTB.EXE`, pre-`--scan-tribe`, trustworthy), `cam4.txt`/`cam5.txt`
(`--scan-tribe` runs, native, trustworthy; `cam5.txt` is the first turn-anchored full-flyby capture).

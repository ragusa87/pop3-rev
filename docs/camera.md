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

### `FLYBY_START`'s turn, anchored three independent ways
1. The script's first `ANGLE` keyframe (`DO FLYBY_SET_EVENT_ANGLE 0 5 35`, i.e. value=0 start=5
   duration=35 turns after `FLYBY_START`) predicts a plateau at `FLYBY_START+40`; the captured yaw
   plateaus at turn ≈119-120, giving `FLYBY_START ≈ 80-ish`.
2. User's own knowledge: the reincarnation centre's intro animation plays turns 0 to about 70, flyby
   starts right after - independently lands in the same range (and matches the script's own
   `IF (INT_GAME_TURN > 70)` gate, `ai-scripts.md`).
3. The `POS`/`ZOOM` channels' own hold windows (see "Joint fit" below) land in the same range once
   fitted.

Working estimate: **`FLYBY_START` ≈ turn 77-80**, ±15, not exact - see "Open questions".

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
| `+0x24` | packed dword, two 16-bit halves move independently | camera focus x (low half), z (high half) | x/z direction confirmed by a joint fit (see below); exact scale/offset not |
| `+0x28` hi 16 bits | wraps like a cyclic angle; flat exactly when pitch is flat even while yaw keeps moving (decisive: turns 185-270, yaw moves freely, this field and pitch both sit dead flat for 85 straight turns) | raw pitch angle | shape strongly correlates with pitch; raw-to-degrees transform not solved - tried simple ratios at two sample points, inconsistent (not a constant scale, not a constant offset from `M21`) |
| `+0x28` lo 16 bits | pinned at constant `0x0065` the whole capture | unrelated adjacent byte/flag | - |
| `+0x2c` | smoothly monotonic, always an exact multiple of `0x10000` in both captures | camera distance/zoom | correlates with the `ZOOM` channel's hold windows; exact scale/offset not fitted |
| `+0x30` | ramps between 0 and exactly `0x1000000` (2²⁴), direction flips at each transition, holds at the max through idle/hold windows | per-segment interpolation progress, 8.24 fixed point (0.0-1.0) | plausible shape, not cross-checked against a ground-truth progress value |
| `+0x34` | grows with an almost-constant second difference (quadratic) during transitions | easing/acceleration counter, maybe the smoothstep curve itself | least certain of the five, could be unrelated noise |

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

## Open questions / next steps
1. **Pin `FLYBY_START`'s turn exactly.** Stop curve-fitting camera motion; find the AI script's own
   per-tribe flyby-active flag (the script sets `$57` right before `DO FLYBY_START` -
   `ai-scripts.md`'s worked example) and read it directly from live memory instead.
2. Solve `+0x28`'s raw-to-pitch-degrees transform (need more samples; two-point ratio checks didn't
   resolve to a constant).
3. Decode the `POS` waypoints' own coordinate units (likely map tiles/cells, not world units) and fit
   the exact scale/offset against `+0x24`'s two halves.
4. Re-run the cancel capture with precisely-timed Ctrl+C'd turn numbers (see "Flyby cancel" above).
5. Apply the D3D axis caveat once position/angle values are solid enough to change `flyby.rs`.

## Raw capture logs
Not committed, scratch only: `cam.txt` (POPTB.EXE, mistranslated address lesson - m1..m8 read stuck
at 0 the whole time due to `addrmap.py`'s anchor+delta fallback being wrong for that struct), `cam2.txt`/
`cam3.txt` (native `D3DPOPTB.EXE`, pre-`--scan-tribe`, trustworthy), `cam4.txt`/`cam5.txt`
(`--scan-tribe` runs, native, trustworthy; `cam5.txt` is the first turn-anchored full-flyby capture).

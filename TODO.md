# TODO

Working list of items from `veritr1x/populous-recomp`'s `globals.toml` (MIT,
https://raw.githubusercontent.com/veritr1x/populous-recomp/refs/heads/main/globals.toml)
that still need independent confirmation before being trusted as-is. See
README.md "Credits" and the matching `docs/functions.tsv` rows for what's
already been cross-checked and added.

All addresses below were matched against our own Ghidra export
(`backup/backup.xml`) only - none of this has been independently traced in
our own disassembly (`dis.txt`) yet, and none should be assumed correct just
because an address lines up.

## Resolved this session (2026-10-28)

All of the "address matches ours, but role not verified" items, and all of
the "exact match, not yet added" items, were independently traced against
`dis.txt`/`backup.xml` this session and their `docs/functions.tsv` rows
updated (name adopted/kept, status raised to `traced` where the role was
actually read, with the reasoning inline in each row - see that file rather
than re-duplicating it here):

- `0x89d184` -> renamed `command_frame` (was `offset_counter`)
- `0x89d188` -> renamed `simulation_turn` (was `offset_counter_2`)
- `0x89c661` -> renamed `game_flags_1` (was `land_flags_1`; bit 0x2 = paused
  confirmed, but it's a general multi-purpose flags dword, not land- or
  pause-specific - neither prior name was quite right)
- `0x8e0428` (`unit_array`) - stride 179 / count 2000 independently verified
  via `backup.xml`'s own `game_state` struct layout math, not just trusted
  from `globals.toml`
- `0x74a350` (`tribe_ptr`) - reconciled with `update_vfconfig` (0x417338) and
  docs/camera.md: it's a tribe_struct pointer whose target doubles as the
  live camera matrix, so both names describe the same thing
- `0x4ec6f0` (`main_loop_inner`) and `0x4a5590` (`main_loop_outer`) - merged
  with pre-existing (unnamed) rows that had already traced their role;
  `on_turn`/`on_frame` naming confirmed accurate for inner/outer respectively
- `0x40c670` (`load_objs_1`) - thunk behaviour read in full, confirms
  `level_startup_thunk` role
- `0x89ce3a`, `0x87ca92`, `0x87caa4`, `0x87caa6` (`current_obj_num`,
  `screen_height_2`, `screen_width_2_half`, `screen_height_2_half`) - added
  as rows, exact address+name matches confirmed, derivation of the two
  "_half" values traced
- `0x45efd0`/`0x45f4a0`/`0x45f9d0` (`set_human_anim_*`) - added as rows,
  exact address+name matches confirmed; function bodies not fully traced
- `0x46dbe0` (`coord_global_convert`) - traced: world-to-view-space point
  transform via the same camera matrix as `tribe_ptr` above
- `0x46f080` (`add_object_to_rendering_queue_type_1_10`) - traced: computes
  a unit's render-interpolation delta, gated by the pause bit above
- `0x4f95a0` (`init_polygon_quad_with_sprite_5a`) - partially traced (reads
  the screen origin, see next item); full body still open
- `0xa68f64` -> renamed `vertex_shift_x` role confirmed as a screen-space
  origin-x offset added to vertex/sprite coordinates, matching
  `globals.toml`'s `display_origin_x` better than our old name

### Previously "no matching symbol" - now confirmed same build, just unannotated

Checked directly against `dis.txt`/`backup.xml` this session, per the old
note's own instruction. None of these are a build/offset mismatch - code
exists at the exact same address in both exports, Ghidra (and we) just never
named it:

- `0x42c6d0` - light trace added (per-tribe teardown call, consistent with
  `on_level_end`, not fully confirmed) - `docs/functions.tsv`
- `0x4b0e80` - light trace added (32-way mode dispatch via remap+jump table,
  consistent with `display_enumerate_mode`, cases unread) - `docs/functions.tsv`
- `0x46daa0` - traced (screen-bounds outcode/clip-flags computation against
  `screen_width_2`/`screen_height_2`, consistent with `display_cull_triangle`)
  - `docs/functions.tsv`
- `0x4f98a0` - light trace added (sprite-record field reads + scaled float
  math, consistent with `display_sprite_resolve` but not confirmed) -
  `docs/functions.tsv`

## Resolved (static only, 2026-10-28) - `0xd0597c`/`0xd05980`/`0xd05978`

Dug further into this one without live memory (none available this session).
The 3 addresses are genuinely absent as independent globals in our build -
but that's because they're not independent globals in the first place: they
sit at the exact same *relative offsets* (+0x1c, +0x20, +0x24) from the base
of a single global C++-style object at `0xd0595c`, found by following the
`DINPUT.dll`/`SetCursorPos`/`SetCursor` imports forward rather than trusting
the flat external addresses. See that address's new row in
`docs/functions.tsv` for the full reasoning - short version: `+0x1c` is a
lazily-allocated 0xf8-byte context pointer (matches `mouse_input_context` in
spirit), `+0x20`/`+0x24` are a DWORD (x,y) pair with a getter/setter pair,
and the object's own buffered-input consumer specifically accumulates
DirectInput's `DIMOFS_X`/`DIMOFS_Y` (offsets 0/4) deltas before reading that
position back - about as strong a static confirmation as this gets that the
object is the mouse-position tracker, and that `globals.toml`'s claimed
roles for these 3 offsets are right, just modeled as flat globals in that
project's build vs. a class member here.

**Not yet live-verified** (no live-memory access this session) - the object
layout (`+0x14`, `+0x28`/`+0x2c`, the `+0x38` rect, the `+0x1c` sub-object's
own 0xf8 bytes) is still open for a session that can watch `0xd0595c` while
moving the mouse.

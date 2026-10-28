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

## Still open

- `0xd0597c` (`mouse_cursor_x`), `0xd05980` (`mouse_cursor_y`),
  `0xd05978` (`mouse_input_context`) - checked this session: genuinely
  **absent** from both `backup.xml` and `dis.txt`, not just unannotated.
  Our exe build does reference the surrounding `0xd05xxx` region heavily
  (500+ distinct addresses there), including bytes immediately on both
  sides of the gap (`0xd05960` and `0xd059b0` both appear, nothing at all
  in between) - so this looks like a real per-build data-layout difference
  for this specific struct/buffer, not a dead reference. Needs the mouse
  input code found independently in our own disassembly (follow whatever
  reads screen-space cursor coordinates) rather than assumed from the
  external address.

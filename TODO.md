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

## Address matches ours, but role/name not independently verified

These rows are already in `docs/functions.tsv` (status `named`) because the
*address* matches a real symbol in `backup.xml`, confirming same exe build -
but our own name differs from `globals.toml`'s, and neither name's claimed
*role* has been independently traced this session. Needs someone to actually
read the code/data usage and settle which name (ours, theirs, or neither) is
right, then update the row's `status`.

- `0x89d184` - ours `offset_counter` vs their `command_frame`
- `0x89d188` - ours `offset_counter_2` vs their `simulation_turn`
- `0x89c661` - ours `land_flags_1` vs their `pause_flags` (bit 0x2 = paused)
- `0x8e0428` - ours `unit_array` vs their `entity_base` (stride 179, count 2000 - stride/count unverified)
- `0x74a350` - ours `tribe_ptr` (Ghidra datatype `tribe_struct *`) vs their `display_camera_ptr` - may relate to the tribe_struct camera field tracked in `docs/camera.md`, not reconciled
- `0x4ec6f0` - ours `main_loop_inner` vs their `on_turn` hook
- `0x40c670` - ours `load_objs_1` vs their `level_startup_thunk` (role agrees: thunk wrapping load_objs)
- `0xa68f64` - ours `vertex_shift_x` vs their `display_origin_x`

## Address exists in backup.xml but not yet cross-checked at all

Found while reading the full `globals.toml`, not yet compared or added to
`functions.tsv`:

- `0x89ce3a` - ours `current_obj_num`, theirs same name - exact match, just not yet added as a row
- `0x87ca92` - ours `screen_height_2`, theirs same name - exact match, just not yet added
- `0x87caa4` - ours `screen_width_2_half`, theirs same name - exact match, just not yet added
- `0x87caa6` - ours `screen_height_2_half`, theirs same name - exact match, just not yet added
- `0x4a5590` - ours `main_loop_outer` vs their `on_frame`/alias `frame_driver`
- `0x46dbe0` - ours `coord_global_convert` vs their `display_project_point`
- `0x46f080` - ours `add_object_to_rendering_queue_type_1_10` vs their `display_queue_entity`
- `0x45f4a0` - ours `set_human_anim_tribe` vs their `display_human_tribe`
- `0x45f9d0` - ours `set_human_anim_tribe_person` vs their `display_human_person`
- `0x45efd0` - ours `set_human_anim_no_tribe` vs their `display_human_unowned`
- `0x4f95a0` - ours `init_polygon_quad_with_sprite_5a` vs their `display_sprite_quad`

## No matching symbol found in backup.xml at all

Could mean: different exe build/offset, or just unannotated in our export
(not necessarily a contradiction). Needs checking directly against `dis.txt`
before drawing any conclusion either way.

- `0x42c6d0` - their `on_level_end`/alias `level_end`; ours has an unnamed `FUN_0042c6d0` at that address (code exists, no role traced)
- `0x4b0e80` - their `display_enumerate_mode`; ours has a code block/bookmark at that address but no symbol name or traced role
- `0x46daa0` - their `display_cull_triangle`; ours has an unnamed `FUN_0046daa0` at that address
- `0x4f98a0` - their `display_sprite_resolve`; ours has an unnamed `FUN_004f98a0` at that address
- `0xd0597c` - their `mouse_cursor_x` - no entry at this exact address in our export
- `0xd05980` - their `mouse_cursor_y` - no entry at this exact address in our export
- `0xd05978` - their `mouse_input_context` - no entry at this exact address in our export

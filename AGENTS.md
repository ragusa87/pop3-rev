# AGENTS.md

Read `CONTEXT.md` first for a big-picture overview before diving into the exe, memory, or docs.

## Role: document only
Agents working from this repo analyse the original game and document it. They never implement anything:
- No code changes in `open-populous` (`crates/`, tests, tools): no fixes, even when asked to "fix" a difference.
- Write the findings to `open-populous/docs/specs/pop3-rev-analysis.md`, the matching spec, and `TODO.md`
  (the items describing what our code should change). The implementation is done in a separate session.
- No commits in `open-populous`: report what changed in each file.

## Docs in this repo
- `docs/functions.tsv`: standalone catalog of exe addresses (one row per function: address, name, feature_area,
  status, role), built incrementally by the `exe-function-map` skill. Never points into `open-populous`.
- `docs/person_states.tsv`, `docs/effect_states.csv`, `docs/controller_states.csv`: catalogs of the `+0x2C`
  per-turn **state** number for each of the three "stateful" unit classes - class 1 (person), class 7 (effect),
  class 10 (internal controller) respectively. These are THREE SEPARATE numbering spaces: the same number means
  a different thing in each file (e.g. person state 24 is Whirlwind's own lift state, effect state 24 is erosion,
  controller states only go up to 18) - always say which class/file a bare "state N" comes from. Update the
  matching file whenever a state's handler or role is traced or corrected, the same way `functions.tsv` rows are
  kept current; `pop3-rev-analysis.md`'s own state write-ups should point at these files rather than re-listing
  every state inline.
- `docs/unit_types`: per-class unit/person/building/etc. type ids and names (a different axis from the state
  catalogs above - `+0x2B` type vs. `+0x2C` state).
- `docs/sound.tsv`: catalog of sound ids, keyed by the `type_id` argument to `0x48A050` (`fn(unit, type_id, flag)`,
  the one confirmed generic "play this sound" entry point - re-verify that assumption if a session ever finds a
  second one). Columns: `sound_id  name  feature_area  status  trigger  role`, same `status`/`feature_area`
  vocabulary as `functions.tsv`. `trigger` is the address(es) of the call site(s) found so far that pass this id
  (a sound id is not a unique key the way a state number is - the SAME id can turn up at unrelated call sites, and
  different ids can sound similar; never assume one id means only one thing without checking). `role` says exactly
  when it plays (the condition at that call site), one line per distinct trigger if there's more than one. Built
  the same incremental, one-session-at-a-time way as the other catalogs, via the `exe-function-map` skill.
- `docs/commands.tsv`: catalog of the game's two player/AI-command dispatch layers, each its own raw-id numbering
  space (always say which `layer` a bare id belongs to, same rule as the state catalogs below): `ui_cmd` is
  `process_cmd`'s own id (a player action - keypress, UI click - read as this function's single argument,
  dispatched via its own remap/jump table) and `tribe_cmd` is `process_tribe_cmd`'s own id (a QUEUED per-tribe
  command, the `cmd_pop` 15-byte opcode+2-args record, drained once per tribe per turn by `process_tribes_cmd` in
  every game mode - not campaign/AI-script-specific, a mistake an earlier session made and corrected). A `ui_cmd`
  case typically ends by calling `set_tribe_command` to queue a `tribe_cmd`, so the two layers chain but are not
  the same numbers. Columns: `layer  id  name  input  feature_area  status  trigger  role` - `input` is the
  known keybind/click (`ui_cmd` only, `-` for `tribe_cmd`, cross-check `open-populous/docs/specs/shortcuts.md`
  for the player-reported side), `trigger` is the case's own entry address plus which dispatch table/index it
  came from, same `status`/`feature_area` vocabulary as `functions.tsv`. Built the same incremental,
  one-session-at-a-time way as the other catalogs. **Check `backup.xml`'s own `SYMBOL` entries before
  reverse-engineering a dispatch table by hand**: Ghidra's analysis already names every switch case it found as
  `caseD_<hex id>` under a `switchD_<switch address>::` namespace (`grep "switchD_<addr>" backup/backup.xml`) -
  this is the literal raw id for that case, for free, and caught a real mistake this session (`0x479DD0` looked
  like a second entry point of `set_tribe_command`/0x479CF0 from its disassembly alone, but `backup.xml` names it
  as a separate function, `set_data_to_rddata_chunk`). A later session worked through the three labeled switches
  `commands.tsv` didn't yet cover (`switchD_0043e93d`/`switchD_004ab6f3`/`switchD_004adda9`, found inside
  `process_tribe_cmd`/`process_cmd`/`FUN_004adbb0` respectively) - results are in `commands.tsv` (tribe_cmd
  0xc/0x1c, ui_cmd 0x9c) and `functions.tsv` (`0x4adbb0`'s own row, the mouse-drag-to-camera pipeline it turned
  out to be part of). Several sub-cases and callees (`0x4e6a70`, `0x479f00`, the per-game-mode cases of
  `switchD_004adda9` itself) are still open leads, not exhausted - `process_cmd`/`process_tribe_cmd` almost
  certainly have further unlabeled switches past these; the `grep "switchD_<addr>"` trick remains the way to find
  the next one's raw case ids for free instead of hand-decoding a jump table.
- `docs/cheat.md`: narrative log of live-memory sessions (blast pushes, damage constants, etc.), not a catalog.
- `docs/camera.md`: working log for the camera/flyby investigation (raw addresses, candidate tribe_struct
  fields, confidence levels, dead ends, tools) - the fuller record behind what's written into `open-populous`
  `docs/specs/pop3-rev-analysis.md` "Camera flyby state (tribe_struct)".
- `backup/backup.xml`: the Ghidra export both skills read function names/ranges from. **It holds much more than that**
  (found by an agent session, previously unused): full `STRUCTURE`/`MEMBER` type definitions for this exact game
  (`unit_struct`, `tribe_struct`, `unit_type_person`, `sprite_bank`, `vstart_struct`/`vfra_struct`/`vele_struct`,
  `objs0_struct`/`pnts0_struct`/`facs0_struct`, and more - grep `<STRUCTURE NAME=` to list them), plus ~19k
  `REGULAR_CMT` comments (almost all Ghidra boilerplate - "Function Signature Data Type" - but a few dozen are
  real human notes, mostly about terrain/sprites). These are worth checking before re-deriving a field from
  scratch: `unit_struct`'s members already confirmed `class_counter`/`unit_type`/`tribe_index`/`state`/`state_2`
  exactly as independently derived, and caught a real mistake - `tribe_struct+0x881` is named `person_units`
  (buildings are a separate list at `+0x885`), not the "building list" several functions.tsv rows had called it.
  Also check its `SYMBOL` entries before hand-decoding ANY jump table (not just for `commands.tsv`): Ghidra names
  every switch case it recognised as `caseD_<hex id>` under a `switchD_<switch address>::` namespace, so
  `grep "switchD_<addr>" backup/backup.xml` can hand you a dispatch table's literal case ids directly, instead of
  reading the jump table's raw bytes and a remap table by hand (`jt.py`'s own method, still needed for tables
  Ghidra didn't recognise as a switch, or whenever `backup.xml` has no entry at that switch address).
  Caveats: coverage is sparse/generic past the first ~0x98 bytes of `unit_struct` (exactly where most per-state
  fields like `+0x70`/`+0xAA`/`+0xAC`/`+0xAD` live), and a member's name can reflect a DIFFERENT unit class's
  usage of that shared offset than the one being checked (this exe reuses offsets across classes/types
  constantly, as the rest of this file's docs already track) - treat names here as a strong cross-check lead, not
  infallible ground truth. Current toolchain is `objdump` disassembly (via the two skills' own `sl.py`/`setup.sh`)
  plus this static XML export - no live Ghidra instance in this environment (not installed as of this note,
  though available via `pacman -S ghidra`/`yay -S ghidra` on this machine, headless analyzer included in the same
  package). A live instance (headless scripting, or an MCP server such as AUR's `ghidra-mcp`) would give a real
  decompiler view and a complete cross-reference graph instead of grep-over-`dis.txt` (which misses indirect
  calls and jump-table-driven calls) - worth setting up if this investigation continues much further.

## Clean-room boundary
The goal is a clean-room reimplementation: behaviour reimplemented without copying the
original's expression of it, so the result isn't a derivative work. Never produce or commit a
literal decompiled/transliterated C or C++ translation of the disassembly anywhere — not in
`pop3-rev`, not in `open-populous`, not even as a scratch/convenience artifact. Every output
stays at the level of behavioural description: pseudocode of control flow, exact
formulas/constants, data layouts, named functions and their one-line role. This applies to the
function catalog (`pop3-rev/docs/functions.tsv`), the state catalogs
(`person_states.tsv`/`effect_states.csv`/`controller_states.csv`), the sound catalog
(`sound.tsv`), the command catalog (`commands.tsv`, all via the `exe-function-map` skill) and the implementable spec
(`pop3-rev-analysis.md`, via the `original-game-spec` skill) alike.

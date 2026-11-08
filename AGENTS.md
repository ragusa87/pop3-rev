# AGENTS.md

Read `CONTEXT.md` first for a big-picture overview before diving into the exe, memory, or docs.

## Where the exe lives
The game executable (`D3DPOPTB.EXE`, the Direct3D build every address in this repo is traced against) lives in
**`game/` at this repo's own root** - gitignored, never committed (the
clean-room boundary below), but persistent on disk across sessions in the same container, unlike a session's own
scratchpad. `setup.sh` (used by both skills) now checks there FIRST, before falling back to a couple of known
local Wine install paths and a bounded filesystem search - run it with no `GAME=` override and it should just
find it. If `game/D3DPOPTB.EXE` is missing (a brand-new container with no persistent disk from a prior session,
or it was never placed there): ask the user to re-upload the game zip (`Populous_-_A_laube_de_la_cr_ation.zip` or
similar, containing `D3DPopTB.exe`/`popTB.exe`/`HW_SW_Select.exe`), extract it, and copy `D3DPopTB.exe` to
`game/D3DPOPTB.EXE` (uppercase - case matters) yourself so it persists from then on, rather than re-deriving a
scratchpad-only copy that won't survive the next session. Also worth checking for the SOFTWARE-renderer sibling,
`POPTB.EXE` (same code, different link order, same `game/` dir) - never analysed directly (`sl.py`/`dis.txt`
assume the Direct3D build), but useful for live-memory checks when it runs better; `docs/poptb_map.tsv` maps
addresses between the two builds.

**Known-good `D3DPOPTB.EXE` builds, by sha256** - none of these match `Makefile`'s own pinned hash, safe to keep
using anyway; each was spot-checked against known addresses rather than trusted on hash alone, so a hash not
listed here needs its own spot-check before being trusted the same way:
- `5234beab740375608ca35bdcd436626f1a6a5677230e1ce7be0fab8f4ef93da5` - spot-checked byte-identical to
  `backup/backup.xml` at several independent landmarks across sessions.
- `3a5065c7420b3fcde208bf220bc86dfbac95e025ab2492caf9c7ea5308dfbe4f` (md5 `6b053fd57e8a90d7717e179fc83f80ad`) -
  **a different build from the one above** (user-confirmed: "the Ghidra analysis is not my version", probably
  v1.03; a GOG release is a third variant the user may upload later, not yet seen in this repo). Spot-checked by
  rebuilding `dis.txt` from it and re-reading 5 addresses already written up from the OTHER build
  (`0x40BD20`/`0x408ED0`/`0x51A2A0`/`0x40BAE0`/`0x407810`, see pop3-rev-analysis.md "Watchtower sentry scan and
  alarm") - every one disassembled to the exact instruction sequence the existing analysis already describes, so
  this build is at least code-identical in the regions traced so far even though its own hash differs. Don't
  assume that extends to the WHOLE exe (e.g. a patched intro/copy-protection stub) without a landmark check in
  whatever region a future session newly touches.

## Role: document only
Agents working from this repo analyse the original game and document it. They never implement anything:
- No code changes in `open-populous` (`crates/`, tests, tools): no fixes, even when asked to "fix" a difference.
- Write the findings to `open-populous/docs/specs/pop3-rev-analysis.md`, the matching spec, and `TODO.md`
  (the items describing what our code should change). The implementation is done in a separate session.
- No commits in `open-populous`: report what changed in each file.

## Docs in this repo
- `docs/functions.tsv`: standalone catalog of exe addresses (one row per function: address, name, feature_area,
  status, role), built incrementally by the `exe-function-map` skill. Never points into `open-populous`.
- `docs/person_states.tsv`, `docs/effect_states.csv`, `docs/controller_states.csv`, `docs/scenery_states.csv`:
  catalogs of the `+0x2C` per-turn **state** number for each "stateful" unit class - class 1 (person), class 7
  (effect), class 10 (internal controller), class 5 (scenery, added when ground fire was traced) respectively.
  These are SEPARATE numbering spaces: the same number means a different thing in each file (e.g. person state 24
  is Whirlwind's own lift state, effect state 24 is erosion, controller states only go up to 18, scenery state 5
  is a tree/plant that has just caught fire while person state 5 is an unrelated "idle near a reference unit")
  - always say which class/file a bare "state N" comes from. Update the matching file whenever a state's handler
  or role is traced or corrected, the same way `functions.tsv` rows are kept current; `pop3-rev-analysis.md`'s own
  state write-ups should point at these files rather than re-listing every state inline.
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
- `docs/weanetr-dll.md`: import catalog for `weanetr.dll`, the exe's external multiplayer-networking library
  (`MLDPlay` class, DirectPlay-flavoured) - all 21 imports with demangled C++ signatures and IAT addresses, found
  via `strings`/`objdump -x`/`pefile`/`llvm-undname` on the exe alone (no live memory, no Wine) when a UI question
  turned out to hinge on an externally-visible action (network send). Same "check the DLL imports first" method
  is worth trying again whenever a question is about what clicking something actually DOES (network, file I/O)
  rather than how the UI looks, especially in an environment without Wine/a display for a live check.
- `docs/camera.md`: working log for the camera/flyby investigation (raw addresses, candidate tribe_struct
  fields, confidence levels, dead ends, tools) - the fuller record behind what's written into `open-populous`
  `docs/specs/pop3-rev-analysis.md` "Camera flyby state (tribe_struct)".
- `docs/trace-backlog.md`: queued tracing targets for a future session, one topic at a time (currently Angel of
  Death and native-AI/AI-scripting follow-ups) - each item names the concrete exe lead to chase, found by reading
  what `open-populous`'s own TODO.md/specs left open after building on a prior session's findings here. Check
  this file before starting a fresh investigation from scratch; add to it (with the same "what to chase, and
  where" shape) whenever `open-populous`'s own docs surface a new open question this repo should resolve, rather
  than letting it go untracked.
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

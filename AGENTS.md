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
- `docs/cheat.md`: narrative log of live-memory sessions (blast pushes, damage constants, etc.), not a catalog.
- `backup/backup.xml`: the Ghidra export both skills read function names/ranges from. **It holds much more than that**
  (found by an agent session, previously unused): full `STRUCTURE`/`MEMBER` type definitions for this exact game
  (`unit_struct`, `tribe_struct`, `unit_type_person`, `sprite_bank`, `vstart_struct`/`vfra_struct`/`vele_struct`,
  `objs0_struct`/`pnts0_struct`/`facs0_struct`, and more - grep `<STRUCTURE NAME=` to list them), plus ~19k
  `REGULAR_CMT` comments (almost all Ghidra boilerplate - "Function Signature Data Type" - but a few dozen are
  real human notes, mostly about terrain/sprites). These are worth checking before re-deriving a field from
  scratch: `unit_struct`'s members already confirmed `class_counter`/`unit_type`/`tribe_index`/`state`/`state_2`
  exactly as independently derived, and caught a real mistake - `tribe_struct+0x881` is named `person_units`
  (buildings are a separate list at `+0x885`), not the "building list" several functions.tsv rows had called it.
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
(`person_states.tsv`/`effect_states.csv`/`controller_states.csv`, all via the `exe-function-map`
skill) and the implementable spec (`pop3-rev-analysis.md`, via the `original-game-spec` skill)
alike.

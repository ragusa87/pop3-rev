---
name: exe-function-map
description: Analyse a function or address in D3DPOPTB.EXE and record what it does in a standalone, local catalog (pop3-rev/docs/functions.tsv) — no dependency on open-populous. Use for exploratory "how does X work" / "what does this function/address do" / "analyse Z" questions where the goal is understanding the exe, not yet producing an implementable spec. For turning a finding into a reimplementation spec, use original-game-spec instead.
---

# Exe function map

Goal: build up, one session at a time, a standalone local catalog of which addresses in
`D3DPOPTB.EXE` are which function and what they do — resumable across sessions, scoped to one
target at a time. This is the first half of the pipeline; it does not touch `open-populous`.

## Paths
- Exe: `~/.wine/drive_c/Program Files (x86)/Bullfrog/Populous - A l'aube de la création/D3DPOPTB.EXE`.
  All addresses here are `D3DPOPTB.EXE` addresses.
- Ghidra export: `pop3-rev/backup/backup.xml`.
- Tools: reuse `.claude/skills/original-game-spec/scripts/` as-is (`setup.sh`, `sl.py`,
  `livemem.py`, `addrmap.py`, `consts.py`) — do not duplicate them here.
- Catalog to write: `pop3-rev/docs/functions.tsv`. Standalone: it never points into
  `open-populous` and nothing in `open-populous` points into it.
- State catalogs to write alongside it, one per "stateful" unit class, whenever the target is a
  per-turn STATE dispatch (`+0x2C`) rather than an ordinary function: `pop3-rev/docs/person_states.tsv`
  (class 1), `pop3-rev/docs/effect_states.csv` (class 7), `pop3-rev/docs/controller_states.csv`
  (class 10). These are three separate numbering spaces - the same number means something
  different in each file; never merge them or assume a state found in one applies to another.
- Sound catalog to write alongside it, whenever a traced function calls `0x48A050` (`fn(unit, type_id, flag)`,
  the one confirmed generic "play sound" entry point): `pop3-rev/docs/sound.tsv`, one row per distinct
  `type_id` seen. Not a per-class numbering space like the state catalogs - the same id can legitimately
  turn up at more than one unrelated call site, so a row accumulates triggers rather than being
  "claimed" by the first function that uses it.

## Setup (once per session)
Same as `original-game-spec`: `bash .claude/skills/original-game-spec/scripts/setup.sh` builds
`dis.txt` (disassembly), `fn.tsv` (Ghidra functions), `consts.txt`/`constant.txt` in `$WORK`
(default `/tmp/pop3-spec`, or `WORK=<scratchpad> bash ...`).

## Scoping & resuming a session
- **Start**: `grep`/skim `docs/functions.tsv` first — check whether the target address or a
  function near it is already catalogued before re-deriving it from scratch. If the target is a
  per-turn state, also check the matching state catalog (see below) for that state number first.
- **One target per session**: one function, or one tight cluster of callees actually needed to
  understand it. Not an open-ended sweep across unrelated systems.
- **Deep dive** means following calls until *that* target's own behaviour is understood. When a
  callee turns out to be its own rabbit hole, log it as a new `named` row (so it's not forgotten)
  and leave tracing it to a later, separate session rather than chasing it now.
- **End**: append or update a row in `docs/functions.tsv` for every function newly looked at this
  session, including dead ends and helpers that won't make it into any narrative write-up. A
  function only partially understood still gets a row — never silently drop it; put the gap in
  a terse `role` instead (e.g. "dispatch table by type; cases 3/5 unread").

## Finding the code
- A constant: `grep -i NAME consts.txt` gives its address; grep that address (or a per-type
  table base plus the field offset) in `dis.txt`.
- Per-type tables are read as `[type*stride + base + field]`; compute the base and grep it.
- A Ghidra name: `grep -i name fn.tsv`, then verify what the code really does — Ghidra names are
  a previous analyst's guesses, often wrong or shifted.
- `python3 scripts/sl.py LO [HI]`: disassembly of a range (one function if `HI` omitted);
  `python3 scripts/sl.py fn ADDR...`: which Ghidra function holds an address.
- When static search stalls, measure live with `scripts/livemem.py` (needs the user to run it
  with `sudo`; give them the exact command).

## Writing `docs/functions.tsv`
Re-read the file first (it's append-only but may have been edited since). Columns:

```
address	name	feature_area	status	role
```

- `address`: `0x...`, the `D3DPOPTB.EXE` address.
- `name`: Ghidra's name if still trusted, a proposed rename if better understood, else `-`.
- `feature_area`: one of `units`, `sprites_anim`, `spells`, `buildings`, `worship`, `vehicles`,
  `combat`, `huts_training`, `objects`, `trees`, `constants`, `file_formats`, `other` — keep to
  this list so the column stays groupable.
- `status`: `named` (plausible name only, logic not read) / `traced` (data flow read, behaviour
  understood statically) / `verified` (confirmed with a live memory check).
- `role`: one short, **self-contained** line — must make sense to someone who has not opened any
  other doc.

Sort by address when rewriting the file (`sort -t$'\t' -k1,1`), append new rows then re-sort.

## Writing the state catalogs
When the target is a class-1/7/10 per-turn state (`+0x2C`), also append/update a row in the
matching file (`person_states.tsv` / `effect_states.csv` / `controller_states.csv`), re-read first
the same way. Columns: `state	name	feature_area	status	handler	role` (person/controller) or
`state	name	status	handler	role` (effect, no `feature_area`) - same `status` vocabulary as
`functions.tsv`, `handler` is the address(es) that actually run when a unit is in that state (a
dispatch-table trampoline address is fine if that's as far as it's been traced), `role` is one
self-contained line. Cross-reference the OTHER class's state of the same number if it would be
easy to confuse them (e.g. "NOT the same as person state 24, see person_states.tsv"). Sort by
state number when rewriting.

## Writing `docs/sound.tsv`
Whenever a traced function's call to `0x48A050` resolves to a literal `type_id`, add or update that id's row
(re-read the file first, same append-then-resort discipline as the other catalogs). Columns:

```
sound_id	name	feature_area	status	trigger	role
```

- `sound_id`: `0x...`, the literal id passed as `0x48A050`'s 2nd argument.
- `name`: a short descriptive name once confirmed (by ear, live) or strongly implied by context, else `-`.
- `feature_area`/`status`: same vocabulary as `functions.tsv`. `status` here means: `named` (seen at one call
  site, condition not fully read) / `traced` (the exact triggering condition is read and understood) /
  `verified` (confirmed by ear against the running game, not just the disassembly).
- `trigger`: the address(es) of the call site(s) found so far (comma-separated if more than one).
- `role`: one line per distinct trigger context - the exact condition under which it plays (e.g. "shaman's own
  landing scream, vel.y <= -100, universal physics touchdown 0x4E6D00") - not just "plays during X system", say
  *when* inside that system.

An id is not a unique key: finding the SAME id at a second, unrelated call site means adding a second `role`
line to the same row (with its own trigger address), not creating a conflict to resolve - sounds are a shared
asset pool, reused across systems the way sprites/object ids are elsewhere in this exe. Sort by `sound_id` when
rewriting.

## Clean-room boundary
Never write out, or keep as a scratch artifact, a literal decompiled/transliterated C or C++
translation of the disassembly. `role` and any supporting notes describe *behaviour* (what the
function accomplishes, its formula, its data layout) in your own words — never a line-by-line
transcription of the original's code. See `AGENTS.md` for the full rule (applies repo-wide).

## Report to the user
A short, direct answer to the question first (the address, the name, what it does), then which
rows were added/updated in `docs/functions.tsv` (and `sound.tsv`/the state catalogs, if touched),
and what's still unverified. If the finding
should also become part of the reimplementation spec, say so and suggest running
`original-game-spec` next — don't write into `pop3-rev-analysis.md` yourself from this skill.

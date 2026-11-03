# Trace backlog

Concrete exe-tracing targets queued up for a future session, found by reading `open-populous`'s own
`TODO.md`/`docs/specs/*.md` (as of `open-populous3@main` commit `fe0d8c9`) for exactly which open questions
an implementation session left behind after building on this repo's Angel of Death and native-AI findings.
Each item below is something a future `exe-function-map`/`original-game-spec` session should chase in the
disassembly - not implementation work (that's `open-populous`'s own job, per AGENTS.md's clean-room split).

Re-check the open-populous source before starting any of these: an implementation session may have resolved
one with a different approach, or a later pop3-rev session may already have traced it - grep `docs/functions.tsv`/
`docs/person_states.tsv`/`docs/effect_states.csv` first the way the skills already instruct.

## Angel of Death

- **Does it dive down to grab a grounded victim, or only ever grab from cruising height?** `open-populous`'s own
  implementation confirmed its grab check is x/z distance only, height never factored in - but the exe trace never
  settled whether the original visibly swoops down first. Chase: the case-5 hunt/engage machine's own grab
  transition (`0x4DB980`, `+0xA8`==1) for any height-target write distinct from the general flight-physics
  altitude clamp (`0x4DDB30`).
- **The literal `AOD_KILL_COUNT` (40) / `AOD_DURATION` (2500-turn) expiry check.** Never located in state 28
  itself. Chase: the still-unopened outer `+0x2D` sub-states (0, 1, 3, 4, 6, 7, 8, 0xA, 0xB nested, 0xF, 0x10 -
  symbols only via `backup.xml`'s own `switchD_`/`caseD_` entries at `0x4DB980`'s own switch address), and
  whether the self-damage cost charged on release (`0x4E0A30`) is actually what ends its life via `LIFE_AOD`
  instead of a separate counter.
- **Can it attack a building at all?** No building-attack path was found inside state 28's case 5. The
  user-reported prison/pyramid/totem exclusion is unconfirmed either way. Chase: the still-unopened per-tribe
  fallback scan's own building-candidate path (the sibling of the person-candidate scan already traced).
- **Can it grab a person riding in a vehicle** (boat/balloon) the way it grabs one in the open? No
  vehicle-eviction call was found anywhere in state 28 or its known callees. Chase: the same per-tribe fallback
  scan above, and whether it has any class-4 (vehicle) branch at all.
- **Does it actually pitch/bank in flight**, or is yaw-only (plus the confirmed cruise/dive mesh swap) really all
  the original does? User-reported in play as looking visually odd ("the angle is strange", flat/no banking).
  Chase: the flight-physics helper (`0x4DDB30`) and the shadow-companion's own facing/bank fields for any rotation
  beyond heading (yaw) - a pitch or roll field would settle this.
- **The exact cruise/dive crossfade timing.** `0x4DE440`'s own model-id toggle (0x45 cruise / 0x3E dive) is
  confirmed, but the blend curve between them was never pinned down (implementation uses a straight linear guess).
  Chase: whatever reads the shadow-companion's own `+0x7C` variant counter (0..5) and `0x40CC30`'s variant
  derivation - is there a multi-step blend table there, or a hard cut per tick.
- **The literal mesh/sprite for the confirmed third "launching/accelerating" pose** (outer sub-state 11's own
  distinct `0x4EE700(companion, hfx 0x45, draw_class 4)` call plus `self+0x36 |= 0x4`) - confirmed to exist in
  code, but its own hfx/model id was taken at face value as "same as cruise" without checking whether draw_class 4
  (vs. the cruise toggle's own draw_class, not previously cross-checked) actually resolves to a distinct mesh in
  the object bank.
- **The 36 "orbiter" spark particles' own per-particle motion**, beyond "scattered, staggered lifetimes
  170/340/510/680/850/1020". Chase: `0x514F60`'s own nested 6x6 spawn loop for the actual per-particle initial
  velocity/direction, if any (current implementation guesses a simple fade-in/fade-out with no real motion).

## Native AI / AI scripting

- **`GIVE_UP_AND_SULK`'s actual retreat/guard behaviour.** Only half-traced: the ON case's "force success" flag
  write is confirmed, but its own callee, `0x41CA10(target_struct)`, was never opened - this is the one place the
  wiki's "everyone guards the shaman" claim could still turn out to be literally true. Chase: `0x41CA10` in full.
- **`SET_ATTACK_VARIABLE`'s exact received value/meaning.** Still only the community wiki's own guess
  (`ai-scripts.md`); `ATTACK`'s own worker function was traced down to its call into `0x4E5FD0`, but the other 12
  `ATTACK` parameters' exact mapping onto the task record (including whichever one feeds `SET_ATTACK_VARIABLE`)
  was never decoded. Chase: `0x4E5FD0`'s own parameter-to-field writes, one by one.
- **The guard/patrol group's actual movement order** (how a marker-assigned group walks or circles while
  guarding). Never found anywhere in the exe trace - `open-populous` currently reuses its own unrelated
  patrol-point mechanism as a stand-in. Chase: whatever task type(s) back `GUARD_AT_MARKER`/`GUARD_BETWEEN_MARKERS`
  (per `ai-scripts.md` "Markers, guards and the base" - these states have no DO-command token of their own, so
  start from the per-type default-fallback table or a fresh sweep of `maybe_ai_func_1`'s still-unidentified task
  ids: 0, 1, 4, 6, 7, 8, 11, 14 were only shape-confirmed, not read to completion, per `for-open-populous.md`
  section 6h's own task table).
- **Whether a guard group is ever replenished after losses.** Current best reading is "no" but this was never
  directly confirmed - would need the same guard/patrol task traced above, once found.
- **The shaman's drum-tower rally/muster-before-attack sequence**, and whether she has any dedicated "guard a
  repair site" behaviour distinct from generic base-defense positioning (live-observed on level 25: builds a drum
  tower, goes inside it, followers gather, and she waits beside it during repairs rather than relocating).
  Flagged by the implementation session as its own substantially bigger investigation, not started. Chase:
  `ai_attack`'s own simplification note (`INT_ATTR_DONT_GROUP_AT_DT`, never read anywhere) as the starting
  thread, plus whatever task evaluator actually orders the shaman into a building (`PUT_PERSON_IN_DT` has no
  engine-side mechanism at all yet - nothing currently issues the shaman a move/enter order).
- **Finish tasks 2, 19 and 27** (shaman positioning, vehicle-hut dispatch, class-4 garrison coordination): each
  confirmed last session to interleave more than one distinct job in a single handler, and none was read to
  completion - this is what's blocking "garrison and vehicle tasks" from being modelled in `open-populous` at
  all (explicitly listed there as "deliberately not modelled yet").
- **The real worker-selection tie-breaking rule** (`0x4F8490`/`0x4F7DC0`'s shared "find N eligible workers"
  family - who gets picked when several idle candidates qualify) and **the exact building-site-search placement
  rule** beyond "a bounded number of random nearby tries" (`0x4F7AA0`). Both explicitly left open by the original
  trace; `open-populous` currently guesses (random site search, idle braves in id order).

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

- **RESOLVED this session.** ~~The literal `AOD_KILL_COUNT` (40) / `AOD_DURATION` (2500-turn) expiry check.~~
  Both fully traced: `+0x97` (duration, init 2500, ticks down every turn except while `+0x63` is set) and `+0xB2`
  (kill count, init 0, incremented once per release in `0x4E0A30`) are checked together in `0x4DB980`'s own
  shared tail (`0x4DD3DE`-`0x4DD47B`) - either one hitting its cap forces the angel into caseD_6
  (`0x4DC805`, a 16-turn countdown) then caseD_7 (`0x4DC899`, the real self-delete: sound 0xB2, spirit-handoff,
  a class-7/type-9 death-puff effect, `delete_unit`/`0x4EF180`). A SECOND, more violent ending shares the same
  check: if the angel is already critically damaged (`+0x93` bit 0x1, set when life <=2) when it would otherwise
  still have time/kills left, it instead shatters its own shadow-companion object (`0x407860`) and detonates a
  real damaging blast (`alloc_unit(7,1,...)` + `0x50B6F0`) at its own position, skipping straight to caseD_7
  without the holding countdown. Also corrected in the same pass: `0x4E0A30`'s throw destination is along the
  ANGEL's own facing, not the victim's as previously written, and `0x4E0A30` charges NO self-damage at all (that
  was unconfirmed speculation that didn't survive a full read). Full write-up: `docs/person_states.tsv` row 28,
  `docs/functions.tsv` rows `0x4db980`/`0x4e0a30`/`0x407860`/`0x50b6f0`.
- **RESOLVED this session: yes, it genuinely dives/climbs to the victim's real height.** The moment case 5 commits
  to a grab (`0x4DB980`, `+0xA8` 0->1), it writes a precise target height into `+0x6A` (victim's own ground height
  `+0x41` plus a fixed grab-point offset `+0x1C`). `0x4DDB30` (`aod_flight_physics`) reads `+0x6A` every tick and
  eases its own planned altitude toward it at a rate computed from distance/speed (decelerating as it closes) -
  layered UNDER the already-known ~100-unit terrain floor, so it dives as low as ~100 units above ground to grab
  someone standing there, never lower. `open-populous`'s own grab-range check can stay x/z-only (the exe's own
  grab RANGE check is also x/z-only, per case 5's already-documented standoff-distance logic) - this only affects
  the VISUAL flight path, confirming the original really does swoop down, which a pure x/z-range implementation
  with a fixed cruise altitude would not reproduce. Full write-up: `docs/person_states.tsv` row 28,
  `docs/functions.tsv` row `0x4ddb30`.
- **Building attack - refined (third follow-up session, prompted by a user-reported memory of tower attacks).**
  The candidate SCAN (`caseD_3`, read to completion in the prior session) still only ever accepts class-1/person
  candidates - no class-2 (building) branch exists in it, so the angel can't target a building as an object
  through that path. BUT the engagement-gate helper (`0x4DADA0`, opened this session) explicitly checks whether
  its locked target is standing on a TOWER's door cell (`0x40A3F0(target, 4)`) and reacts with a wider standoff
  distance - confirming the user's memory: **it does go after people sheltering in towers**, just still as a
  person-target, never damaging/destroying the tower itself. Full write-up: `docs/person_states.tsv` row 28,
  `docs/functions.tsv` rows `0x4dada0`/`0x40a3f0`.
- **Vehicle-passenger grab - substantially resolved this follow-up session.** Found and fully traced the actual
  boarding/disembarking pair (`0x4657D0`/`0x4659D0`, `docs/functions.tsv`). A boarded passenger stays a completely
  ordinary, fully-alive class-1 record - nothing unlinks it from the per-cell object chain, so the angel's own
  panic scan (`0x4DB5E0`) CAN in principle reach a boarded passenger. But disembarking is an explicit, active
  function requiring a destination from its caller, not something that happens passively - no call to it, nor any
  clearing of the passenger's own "attached to vehicle" reference, exists anywhere in person state 26's own
  entry/tick code or in the angel's panic scan. **One of disembark's ~17 call sites sits directly inside
  `delete_unit` (`0x4EF180`)** - confirming that destroying/deleting ANY unit, a vehicle included, evicts its
  passengers as generic cleanup, regardless of cause of death. Best current explanation for the user's "panic
  causes people to jump off vehicles" memory: more likely this generic delete-time eviction (a boat/balloon
  destroyed in combat dumps its riders - easy to misread as "they panicked and jumped") than the panic effect
  itself causing a disembark. **Still open**: whether forcing a boarded passenger into state 26's speed/heading
  fields (while still attached) has any visible side effect at all - not checked, but likely none since nothing
  clears the attachment reference; and none of disembark's 17 call sites besides `delete_unit` were individually
  surveyed. Full write-up: `docs/person_states.tsv` row 28, `docs/functions.tsv` rows `0x4657d0`/`0x4659d0`.
- **RESOLVED (simulation side): yes, real pitch and bank ARE computed, not yaw-only.** `0x4DDB30` eases two
  further fields on the companion every tick via the engine's generic tilt helper (`0x4E6C80`, also used by the
  sinking-building rock animation): a speed-dependent nose-up pitch (`+0x6C`, grows the slower the angel flies,
  with a steeper scripted override during the one-time player-approach intro) and a turn-rate bank (`+0x6E`,
  scaled from the desired-vs-current heading delta). Both are skipped (stays level) while carrying a victim or
  during the fast post-grab chase. Full write-up: `docs/functions.tsv` row `0x4ddb30`, `docs/person_states.tsv`
  row 28. **Still open, and this is plausibly the real explanation for the user's "looks flat" report**: whether
  the renderer actually reads `+0x6C`/`+0x6E` to rotate the drawn mesh at all - no other reference to either
  offset was found anywhere else in the executable. Chase: the class-6 object's draw/transform code (find what
  actually builds its render matrix - candidates not yet checked include whatever function services the drawable
  record `0x4EE700` sets up, or the generic per-object 3D transform near `coord_global_convert`/`0x46DBE0`) to see
  whether it reads these two fields, reads something else, or only ever applies yaw.
- **RESOLVED this session (prompted by a user request to catalog the spell's visual effects): cruise/dive
  crossfade timing, and the third "launching" pose.** `0x4DE440` was fully read: the transition is a genuine
  discrete multi-pose blend, not a linear interpolation or a hard cut - a 0..5 counter (`+0x7C`) steps by 1 per
  tick toward the requested pose, passing through 3 intermediate blend poses (indices 76/77/78 via `0x40CC30`,
  also newly traced - a plain field-setter, not a "derivation" function as previously guessed) before swapping to
  the real cruise/dive mesh once the counter reaches its target extreme - up to 5 ticks total. The third pose is
  confirmed as a genuinely separate mesh (model id 0x4A/74, not "same as cruise"): set directly/instantly (no
  blend) by outer caseD_a (`0x4DCCBE`, raw `+0x2D`==11, a climb-out state - snap to ground height, then climb to
  +600 units). Full write-up: `docs/person_states.tsv` row 28, `docs/functions.tsv` rows `0x4de440`/`0x40cc30`.
- **RESOLVED this follow-up session: orbiter count AND per-particle motion, both fully traced.** Count corrected
  to 42, not 36 (6 lifetime/amplitude tiers x 7 angular-phase steps - the previous "36"/"6x6" read the inner
  loop's trip count wrong). Found and read the orbiter's own per-turn body (`0x514D00`, effect state 57/`0x39` -
  not located in the prior session, found this time via `backup.xml`'s own `switchD_0050a769` case symbols sitting
  right next to ground-shockwave's and the meteor's own). Genuine two-phase motion, correcting the earlier
  "scattered jitter, no real motion" guess: while the meteor (its "owner", `+0x6E`) is still alive, each particle
  holds a FIXED relative offset in a 42-point formation trailing the meteor's current position every tick (a
  2-angle sin/cos combination using its own spawn-seeded phase/tier values - the angle-ADVANCE term that would
  make it actually spiral is left at zero and never set, so the formation itself doesn't rotate); the instant the
  meteor self-destructs on impact, every particle independently rolls a random speed/heading, pops up slightly,
  then falls under a simple decelerating arc until it crosses real terrain height and self-destructs. So: a static
  spark-shower formation that detaches and scatters to the ground all at once at impact, not a per-particle
  staggered fade. Full write-up: `docs/functions.tsv` rows `0x514d00`/`0x514f60`, `docs/effect_states.csv` rows
  57/59.

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

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
  row 28. **RESOLVED this follow-up session: yes, the renderer reads and applies both.** Found it via
  `draw_unit_on_land_pos`/`0x46EC80` (the per-frame per-thing draw-state dispatcher) -> `object_to_polygons`/
  `0x4708D0` (reached unconditionally, for the companion's own draw class 4, through the `0x74A348`
  function-pointer slot). That function composes a Z-axis rotation from `+0x6C` and a Y-axis rotation from
  `+0x6E` onto the thing's own 3D orientation matrix (via `create_z_rot_matrix3x3`/`0x47F930` and
  `create_y_rot_matrix3x3`/`0x47FA30`, each a matrix-multiply through `0x47F7B0`) every time it's drawn - skipped
  only for class-2/building objects (a drawable flag, `+0x35` bit 0x20, that the companion never gets set, since
  `alloc_unit` zeroes it and nothing in the angel's own spawn code touches it), which instead get a simpler
  yaw-only path matching the sinking-building rock animation already documented elsewhere. The companion's model
  id also indexes a 54-byte-stride per-model table (`0x895EC1`), confirming it's drawn as a real 3D mesh, not a
  2D sprite - so there's no rendering-side disconnect: the original engine genuinely tilts and banks the angel's
  flying body. Whatever drove the user's original "looks flat" report, it isn't this. Full write-up:
  `docs/functions.tsv` rows `0x46ec80`/`0x4708d0`/`0x471c40`/`0x42a070`/`0x47f930`/`0x47fa30`/`0x47f9b0`,
  `docs/person_states.tsv` row 28.
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

- **RESOLVED this session: `GIVE_UP_AND_SULK`'s real unit-level effect, and the wiki's claim is false.**
  `0x41CA10` (the ON case's own callee, confirmed to take the whole tribe_struct, not a single target) fully
  traced: there is no retreat, guard, order reassignment or formation anywhere in it. It's a tribe-wide sweep that,
  per person: forcibly disembarks any non-shaman follower from a vehicle (`0x466C80`/`disembark_vehicle`), rerolls
  an Angel of Death's own life down to 32-95 (crippling it, via the shared LCG), re-times a currently-hypnotised
  unit's revert countdown (`+0xAC`) to 8-71, deletes any ghost outright (the generic ghost-cleanup convention),
  and reveals/reverts a spy's own disguise (`0x4DE7F0`); separately, a second pass force-deletes any of the
  tribe's own "soul convert 2" (class 10/type 0xC) conversion-coordinator objects in sub-state `+0x75`==7. Net:
  "giving up" is a bundle of cleanup/punishment actions, not a self-contained surrender-and-defend routine - the
  community wiki's "everyone guards the shaman" description does not hold up anywhere in this command's code.
  Significant enough to affect open-populous's own modelling of this command if it's implemented at all (currently
  it isn't, per `ai-scripts.md`). Full write-up: `docs/functions.tsv` rows `0x41ca10`/`0x48e6a1`/`0x466190`/
  `0x466c80`/`0x4de7f0`. (Side correction found along the way: the global object list at `0x890324`, previously
  described in the Angel of Death write-up as "the global type-8 angel list," is actually the exe's generic
  all-objects id-list - dozens of unrelated readers exe-wide filter it by their own class/type, it isn't
  angel-specific; doesn't change any Angel of Death conclusion, since that investigation's own filtering by
  class 1/type 8 was already correct.)
- **RESOLVED this session: `SET_ATTACK_VARIABLE`'s real mechanism, and it's NOT the battle outcome.**
  `SET_ATTACK_VARIABLE $v` is a pure "register" opcode: it stores `$v`'s own variable-slot id into a per-tribe
  staging field (`tribe+0x5A8`) that has exactly one writer in the whole exe and is never reset - so the
  registration is STICKY across every subsequent `ATTACK` call in that script, not a one-shot pairing. Each
  `ATTACK` call (`0x4E5FD0`) reads that staged id at each of its 4 exit points and writes a literal result code
  into it via the generic script-variable-store primitive (`0x48C650`, `script_vars[tribe_idx*3138+var_id]`,
  base `0x9607B2`): **0 = attack task successfully queued, 1 = already at this tribe's per-ATTACK concurrency cap
  (`0x4627F0`'s own per-task-type gate), 2 = no free AI task slot (10 per tribe), 3 = no valid target found
  matching `target_type`.** So `ai-scripts.md`'s "a variable the AI may update with the attack's outcome" was
  roughly right in spirit but imprecise: it's the immediate accept/reject status of the `ATTACK` call itself,
  not the eventual battle's result (kills, damage, win/lose) - a meaningfully different, now-precise answer.
  Side finding from the same pass: `m3` (`ATTACK`'s 13th/last parameter) is confirmed to be read past (PC
  advanced) but never actually resolved or used anywhere - not just unused in practice, the original interpreter
  itself discards it, confirming `ai-scripts.md`'s own "(?)" doubt about it. The broader "other 12 ATTACK
  parameters' exact mapping onto the task record" question is still open beyond `target_type` (now confirmed
  tested directly in `0x4E5FD0`) - most get written into dedicated per-ATTACK task-slot fields rather than
  `set_sub_struct`'s 3 generic params, but which field is which wasn't fully mapped. Also found and fixed a
  pre-existing error in this catalog: `get_tribe_sub_struct`/`0x462730` had its return polarity backwards
  (it returns the first FREE slot, not the first occupied one). Full write-up: `docs/functions.tsv` rows
  `0x48cf50`/`0x48c650`/`0x4e5fd0`/`0x4627f0`/`0x462730`/`0x462d40`. Chase: `0x4E5FD0`'s own parameter-to-field writes, one by one.
- **RESOLVED this session: the guard/patrol group's actual movement order - confirmed ABSENT, not just unknown.**
  Chased by fully tracing task 24's (`0x4cedd0`, `SET_MARKER_ENTRY`/`MARKER_ENTRIES`/`GUARD_AT_MARKER`/
  `GUARD_BETWEEN_MARKERS`'s own native handler) previously-unread "between m1/m2" gather sub-dispatch
  (table `0x4cf2c4`) and all three of its own finalize variants (state 5, keyed on task-record flag `+0x2a`
  and whether `m2==-1`), plus every function any of those paths call (`0x4f3880`/`0x4f8490`/`0x4e9b40`/
  `0x4f2440`, all now traced - see their own `functions.tsv` rows). **None of them ever call `group_alloc`/
  `order_set`/`group_assign` (`0x436c20`/`0x438730`/`0x436d00`) or the player's own patrol-point assigner
  (`0x4ba9b0`) - no movement/walk/circle order is issued to the gathered troops in EITHER mode (circle-m1 or
  between-two-markers).** Troops are recruited by proximity (the shared `0x4f8490` worker-finder) and committed
  into person state 14 ("committed to a job" marker) - and `person_states.tsv` row 14 confirms state 14's own
  per-turn handler is a content-free idle/fidget cycle (cosmetic sub-state alternation on a random timer, no
  movement, no destination field). One narrow exception: the circle-m1 finalize path calls `0x41b180` (own row)
  to release ONLY type-4 (preacher) state-14 units back to their own per-type default behaviour (state 10,
  `order_execute`) - braves/warriors/firewarriors committed by this task are never released by it at all, and
  the between-two-markers finalize variants release nobody, of any type. **Net: the recruited "guard group"
  literally just stands wherever the proximity search found it and fidgets in place - there is no native
  circuit-walking/patrolling behaviour anywhere in the exe for this command family.** This is a genuinely
  different (in fact, nonexistent) mechanism from the player's own 8-slot patrol-point system (`0x4ba9b0`,
  `docs/specs/units.md` "Patrol orders") that `open-populous` currently reuses as a stand-in approximation - so
  that stand-in is not secretly "the same mechanism after all," it is inventing behaviour (actual back-and-forth
  walking) the original engine never implements for this command. Full write-up: `docs/functions.tsv` row
  `0x4cedd0` (updated), `0x41b180`/`0x4e9b40`/`0x4f2440` (new rows), `docs/person_states.tsv` row 14 (cited,
  not changed).
- **Whether a guard group is ever replenished after losses - now moot.** With no ongoing guard/patrol behaviour
  at all (units simply idle after being recruited), "replenishment" isn't a meaningful question for this task;
  nothing resembling a top-up was seen in any of the traced paths above.
- **RESOLVED this session: the gather-then-attack muster sequence, confirming the user's own hypothesis.**
  `0x4CB400` (`ATTACK`'s own task-20 handler, `docs/functions.tsv`'s own row has the full state-by-state
  write-up) turns out to be a genuine 24-substate machine, not just the "per-person sweep" a past session partly
  read. The real sequence: init/wait -> a GATHER phase (one unit-TYPE category per tick, each a percentage-of-budget
  quota - the same `INT_ATTR_PREF_*_PEOPLE`-shaped mechanism `TRAIN_PEOPLE` already uses - committing each found
  recruit to person state 14, plus a final any-type top-up for the remaining shortfall; advances once the force is
  merely non-empty, not once a hard headcount is hit) -> broadcast/commit -> a REGROUP-AT-m1 loop (confirmed as a
  genuine repeating poll, re-kicking stragglers still waiting in state 14, matching `ai-scripts.md`'s already-written
  "it leaves, regroups at `m1`... then attacks" narrative with a concrete state-machine home for the first time) ->
  the per-person sweep issuing real attack orders. **So: yes, units gather (by type quota, not a flat headcount),
  and once the gathered force is non-empty and has regrouped, the attack actually starts - the user's hypothesis is
  correct in substance**, with the gather threshold being "at least one recruit after one pass" rather than "the
  AI's full ideal force." `INT_ATTR_DONT_GROUP_AT_DT` (attribute id 1042): no gating check was found anywhere in
  the entire gather phase (substates 0/2/3/4/5, all fully read) - confirms it's never actually consulted by the
  native `ATTACK` implementation, at least for skipping the gather step itself (substates 9-16/18-23 weren't
  individually read, so not 100% exhaustive). **`PUT_PERSON_IN_DT`'s own missing engine mechanism is STILL
  unresolved** - the shaman's own branch within the per-person sweep (`0x4CC553`, own row, the natural place to
  look) turned out to be something else entirely: she reuses her own auto-cast spell-casting pipeline (the exact
  same gates/cast-call her dedicated auto-cast task, `0x4C9580`, already uses) to cast one of `ATTACK`'s own
  `spell1`/`spell2`/`spell3` operands - not a drum-tower occupancy order. So "whatever task evaluator actually
  orders the shaman into a building" remains an open question for a future session; the "guard a repair site"
  half of this item was not investigated this session either. Full write-up: `docs/functions.tsv` rows
  `0x4cb400`/`0x4cc553`/`0x4d14f0`/`0x4f4680`/`0x4f4f60`/`0x4f4ff0`/`0x4f5050`, plus caller cross-references added
  to `0x4c29a0`/`0x4c2d80`/`0x4f2100`/`0x4f3040`/`0x4f4de0`.
- **Finish tasks 2, 19 and 27** (shaman positioning, vehicle-hut dispatch, class-4 garrison coordination): each
  confirmed last session to interleave more than one distinct job in a single handler, and none was read to
  completion - this is what's blocking "garrison and vehicle tasks" from being modelled in `open-populous` at
  all (explicitly listed there as "deliberately not modelled yet").
- **RESOLVED this session: the worker-selection tie-break is PROXIMITY, not id order.** `0x4F7DC0` (finds at
  most one worker - its own `count` argument can only be 0 or 1, anything else bails immediately) and `0x4F8490`
  (finds up to a real N, via its own `mode` argument) share the same eligibility filter but each have TWO
  selection modes: a plain list-order pass (id order - `0x4F7DC0`'s `count=0`, `0x4F8490`'s `mode=0`) and a
  genuine nearest-neighbour search by toroidal distance to a target position (`0x4F7DC0`'s `count=1`, with an
  18-cell "close enough" early-exit; `0x4F8490`'s `mode=1`, a real top-K insertion sort via its own helper,
  `0x4F8390`). **Every real call site found uses the proximity mode**, confirmed directly for `CONSTRUCT_BUILDING`'s
  own worker-assignment call (disassembled directly: `mode=1`). So `open-populous`'s current "idle braves in id
  order" guess is the WRONG mode - the real rule is "closest eligible worker(s) to the target," and the id-order
  code path, while real, appears to be dead in practice. Full write-up: `docs/functions.tsv` rows
  `0x4f7dc0`/`0x4f8490`/`0x4f8390`, plus 7 new eligibility-callee stubs (`0x4f3200`/`0x4f39d0`/`0x4f55d0`/
  `0x4f61f0`/`0x4f62c0`/`0x4f6720`/`0x4f25b0`) logged but not individually traced.
- **RESOLVED, already fully traced by an earlier session - this backlog item was stale.** "The exact
  building-site-search placement rule" beyond "a bounded number of random nearby tries" is NOT actually open:
  `0x4F7AA0` (`docs/functions.tsv`'s own row) was already fully traced - a deterministic spiral search
  (`0x49C890`) with terrain-suitability (`0x4F3DC0`) and footprint (`0x4B9A20`) checks per candidate cell, plus
  an extra water-adjacency check (`0x4F6B50`) for vehicle-hut building types - NOT a random search as
  `open-populous` currently guesses either. No new tracing needed; `open-populous`'s own "random site search"
  guess should be corrected to "deterministic spiral search from a per-tribe anchor point."

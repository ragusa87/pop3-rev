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

- **"Statue to AoD" effect, follow-up session.** A `0x479890`-spawned Angel-of-Death-typed object (class-1/type-8,
  bypassing `create_aod`, driven to outer raw +0x2D=0xA) - **RESOLVED: caseD_A ("climb-out") fully traced,
  `person_states.tsv` row 28.** It is NEVER a functional hostile hunter: because the statue effect never runs
  `init_unit_class_1`'s type-8 init, the spawned angel's own `AOD_DURATION` (`+0x97`) stays at 0, which the shared
  tail (`0x4DD3DE`) unconditionally treats as instant expiry - each spawned angel gets exactly one tick of its
  dramatic launch-climb pose, then is redirected into the ordinary 16-turn graceful retirement (caseD_6) and
  self-deletes (caseD_7, sound `0xB2`) ~17-18 ticks after spawning, never reaching the hunting loop
  (caseD_1/3/4/5). The statue's own stale-reference re-check almost certainly respawns a fresh one each time,
  so the real visible effect is likely a repeating cycle of short-lived angels, not one persistent one - not
  confirmed live. **Both leads once listed here are now resolved** - see the two "traced to completion" bullets
  below: the first (`FUN_004A9D90`) turned out to be a false lead, corrected with a replacement lead; the second
  (`0x4A66C0`/the "f1" byte mutation/caseD_b) is fully traced, down to one small remaining sub-item (what reads
  the "f1" byte itself) now narrowed to a concrete next step rather than left open-ended.

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
- **`0x4A9D90` traced to completion this session - corrects, rather than confirms, the lead below.** It is a
  generic "set/toggle a named option by id" dispatcher, not an alloc site at all: the literal `0x5b`/`0x63` it
  pushes are `process_cmd` dispatch ids (`ui_cmd`), not class-7 effect TYPE values. Decoded process_cmd's own
  remap/jump tables precisely (`docs/functions.tsv` row `0x4a9d90` has the full method): id `0x63` lands on the
  ALREADY-TRACED, unrelated `commands.tsv` `ui_cmd 0x63` row (a turn-counter-gated pause/resume-ish toggle); id
  `0x5b` lands on process_cmd's own shared NO-OP/unhandled-id fallback - does nothing. **The "untraced alternate
  type 0x63" does not exist**, and `0x4A9D90` has no connection to the Angel-of-Death statue set-piece - the
  shared flag `0x89C661` bit `0x8` is just the general, pervasively-checked "cheat mode enabled" bit, not a
  signal unique to this set-piece. **New lead replacing it**: the real alloc site for class-7 type `0x5b` is
  still unlocated - the literal `push 0x5b` appears exactly once in the whole exe (the now-corrected
  `0x4A9D90` site) and NONE of the 106 `alloc_unit(class=7, ...)` call sites push a literal type immediate of
  `0x5b` either, so the real spawn must compute the type in a register rather than an immediate - most plausibly
  level/script-driven (the same pattern `CALL_TO_ARMS`/`0x48E2B7` already shows for a different native hand-off).
  A future session should walk the register-typed (non-immediate) `alloc_unit(class=7, ...)` call sites - or
  check `interpret_script`'s own opcode table for one whose argument feeds a class-7 type - to find it. Also
  found and named along the way, a tangential but confirmed correction: `alloc_unit`/`0x4ED8A0` does NOT lack a
  per-class init dispatch as a previous session's row claimed - it conditionally calls a newly-named generic
  dispatcher (`init_unit_class`/`0x4ED580`, own new row) unless global `0x89CE37` is set.
- **`0x4A66C0` and caseD_b (`0x4DCE7D`) both traced to completion a later session.** `0x4A66C0` (`functions.tsv`
  own new row) is a shared "configure a scenery object's drawable + render flags" helper, also used by the
  Reincarnation Centre pillar init - for the statue's own call `(statue, 10, 157)`, it sets up the statue's
  drawable via `0x4EE700` and copies `objs0_struct[157].+0x7` (confirmed a DIFFERENT field from the "f1" byte at
  `+0x6` - sibling properties in the same per-mesh-type row, not the same value) onto the statue's own `+0x3B`.
  **This does not explain the "f1" byte itself** - narrowed, not resolved: a future session should search
  specifically for a byte READ at `objs0_struct_row_base+6` (not just the table-base load alone, which 104
  unrelated call sites across the exe also do) to find what actually consults it.

  **RESOLVED (as far as static search allows), later session: nothing in the exe's own code ever reads "f1"
  (`objs0_struct+0x6`).** `backup.xml` turns out to already carry a full human-authored `objs0_struct` layout
  (`<STRUCTURE NAME="objs0_struct" SIZE="0x36">`) - `+0x6` is literally named `f1` there too (an earlier analyst
  didn't resolve it either), `+0x7` is `morph_index`, `+0x2c` (read constantly elsewhere in this catalog, e.g. the
  Blast/Firestorm fireball rows) is `shapes_index`. Walked all 104 loads of the table's own pointer variable
  (`0x895EC1`/`objs0_mem`) exe-wide checking for a subsequent `+0x6` byte read: none exist anywhere - only the 2
  already-known writes (both inside the AoD statue-crumble effect) ever touch it. Its neighbour `morph_index`
  (`+0x7`), by contrast, is read/written in at least 12 separate functions - genuinely used, unlike `f1`. Best
  supported conclusion: `f1` is dead/write-only in this exe build (can't rule out a Direct3D-side consumer this
  search method is blind to, but none exists in the CPU-side code). Full write-up: `docs/functions.tsv` row
  `0x4a66c0`. `caseD_b` (`person_states.tsv`
  row 28, full write-up there) turns out to be a 5-angel squadron spawn-and-launch sequence (a leader spawning 2
  wingmen in a flanking V-formation, each of those spawning one more, then the leader joining the ordinary
  hunting loop while the 4 escorts are routed into a newly-found, still-unopened case, raw `0x11`) - **confirming,
  not contradicting, the "may be dead code for this spawn path" suspicion**: the statue's own hand-spawned angel
  never survives long enough (its `AOD_DURATION` is never initialized) to reach raw `0xB` at all. Also corrected
  in `person_states.tsv` row 28 along the way: caseD_b's own raw value is `0xB` (11), not the `12` a prior
  session's text claimed - confirmed via `backup.xml`'s own `caseD_b` switch-case symbol.
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

- **RESOLVED, later session: the long-open "real alloc site for class-7 type `0x5B` ('statue to AoD')" question -
  there is no runtime alloc site at all.** Exhaustively walked every `alloc_unit` call site in the exe (~188
  total: 107 with a literal `push 0x7` class immediate, the rest register/table-driven for class and/or type) -
  none compute `0x5B` except one, `load_level2`'s own generic per-"thing" loader (`0x485011`, new
  `functions.tsv` row). That function reads class/type/tribe as three adjacent raw bytes straight out of each
  level file's own thing record while parsing a level at load time - **a "statue to AoD" effect is simply
  something a specific level file places directly as an ordinary thing, the exact same mechanism that places
  every person/building/scenery/effect in a level, not a scripted PopScript opcode or a native hand-off like
  `CALL_TO_ARMS`.** This fully explains why the literal byte `0x5B` could never be found anywhere else in the
  exe's own code or static data: it genuinely is level content, not exe content, and this container has no level
  files to check which campaign level(s) actually place it. **This closes the question as far as static exe-only
  analysis can go** - finding WHICH level(s) use it would need an actual level file, out of scope here. Also
  mapped (along the way, same `load_level2` per-thing loop): the per-spell "which effects does casting this
  spell spawn" table (`0x5A80D0`, stride `0x3E`, 5-byte effect-type array at row offset `+0x28`) for spell types
  0-30, confirming `0x4C23E0`'s own existing row's Blast example byte-for-byte (`[0x5,0x3,0x4e,0x26,0]`) - useful
  as ground truth for any future table-driven alloc-site hunt, but contains no `0x5B` either. Side finding, not
  itself about this effect: `load_level2`'s own CLASS==1 (person) loading branch shows that enabling the
  `0x89C661` bit `0x8` "BYRNE" cheat flag before loading a level forces every level-placed person except shamans
  (type 7, which gets a tribe remap instead) to a tribeless wildman - not live-verified, not yet cross-checked
  against `pop3-rev-analysis.md`'s own cheat-mode documentation. Full write-up: `docs/functions.tsv` rows
  `0x479840`/`0x485011` (new).

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
  `0x48cf50`/`0x48c650`/`0x4e5fd0`/`0x4627f0`/`0x462730`/`0x462d40`.
  **RESOLVED, a later session: the other 12 ATTACK operands' own field mapping, read directly from `0x4E5FD0`'s own
  code plus its caller `0x48FC50`'s argument-push order (`add esp,0x38` = 14 pushed args, not 13 - `0x48FC50`
  prepends the tribe pointer, then `team`, then the 11 real resolved values `num,target_type,model,damage,spell1,
  spell2,spell3,attack_type,bring_back,m1,m2`, then a 14th slot that is NOT `m3` but a stale re-push of `m2`'s own
  resolved value, since `m3`'s resolver call is skipped - sharpening the earlier `m3`-discarded finding: no
  placeholder is even pushed for it).** `team` resolves to the TARGET tribe's own struct pointer (its `tribe_idx`
  -> slot+0x54); `num` -> slot+0x6C (via `set_sub_struct`'s `param_b`); `target_type` -> slot+0x58 (raw, alongside
  already-confirmed branching); `model` -> slot+0x59 (raw; also the MARKER index when `target_type==0`, and its
  `0x4C7`/1223 sentinel is confirmed to be exactly `ai-scripts.md`'s own `INT_NO_SPECIFIC_BUILDING` token id);
  `damage` -> slot+0x70 (via `param_c`, a DWORD despite `set_sub_struct`'s own row calling it `param_c_word`);
  `spell1/spell2/spell3` -> slot+0x55/0x56/0x57; `attack_type` -> slot+0x5C (force-overridden to 1 if attacking
  the enemy shaman while she's on a vehicle; remapped into a derived slot+0x5F); `bring_back` -> slot+0x5D; `m1`
  -> slot+0x44 (resolved through the marker-position table `0x89B7A5`, or sentinel `0xFFFF` if -1); `m2` ->
  slot+0x65 (raw - NOT looked up in the marker table, unlike `m1`); `m3` reconfirmed never passed, and the stray
  14th argument (the stale `m2` duplicate) lands in slot+0x66, so that byte isn't a genuine operand either. Also
  resolved `set_sub_struct`'s own `param_a` (slot+0x68): the resolved target's own `+0x24` id word, 0 for MARKER.
  Every field in the previously-flagged `+0x44..+0x67`/`+0x7E..+0x83` range is now accounted for: the ones not
  listed above are either the derived target position (+0x46/+0x50), the `SET_ATTACK_VARIABLE`-staged variable id
  frozen at creation (+0x4E), per-tribe AI tuning-constant-table defaults unrelated to the script
  (+0x60-0x63/+0x7E-0x83), a hardcoded 0 (+0x64), or two one-shot global per-tribe flag bits consumed on task
  creation (+0x67) - none of these are script-controlled. Two things found but NOT chased this session: a sticky
  per-tribe override path (`tribe+0x5B0`/`+0x5AC`/`+0x5AA`) that can replace the derived target position, staged
  by some other not-yet-identified opcode; and an open structural question over whether the generic task-record
  fields (+0x68 onward) genuinely fit within the 82-byte per-slot stride `0x4623E0`/`0x462730` otherwise use, since
  `+0x85` (the task-type tag) exceeds it - doesn't affect any mapping above, but worth a future session if another
  task type's own field ever appears to collide with these. Full write-up: `docs/functions.tsv` rows `0x4e5fd0`
  (extended) and `0x462790` (extended).
  **Addendum, a later session: a 5th result code found, confirming a user hypothesis about vehicle-attack
  gating.** `ATTACK`'s own transport/vehicle-readiness sub-state-machine (`0x4cceb0`, previously undercredited as
  just "a pass-through to `0x4ce2c0`" - own row now) writes **code `6` = "not enough vehicles of the required
  type"** via the SAME `0x48c650` primitive, when a vehicle-based attack (`ATTACK_BY_BOAT`/`ATTACK_BY_BALLOON`)
  doesn't have enough ready vehicles of the needed model - the exact same ceiling-division-vs-owned-count check
  tasks 19/27 (`0x4caac0`/`0x4cf970`) use in their own entry gates. Confirms `tribe+0xba5[model]` (the field both
  tasks 19/27 and this check read) is a LIVE, continuously-recounted headcount of the tribe's own vehicles of
  that model (traced to its writer, `0x4ecac0`'s own per-tribe recount pass, class-4 dispatch case) - not a
  script-configured "intends to attack by boat" flag as first guessed. **The actual relationship**: `ATTACK`
  checks whatever vehicle stock already exists at the moment it's needed and simply fails (reporting code 6) if
  short - it does not wait for or trigger tasks 19/27 to build more. Tasks 19/27 are independent, continuously
  running maintenance keeping the fleet topped up ahead of time. Separately confirmed (already-documented,
  `0x4e5580`'s own row): the AI's top-priority "construct essential buildings" check unconditionally tries to
  maintain a minimum count of boat huts (building type 13) and air/balloon huts (type 15), same as towers (type
  4) - building the HUT itself is baseline infrastructure, not gated on whether an attack is ever planned either.
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
- **RESOLVED (later session): `PUT_PERSON_IN_DT`'s own engine mechanism - found, and it was never in `ATTACK` at
  all.** The earlier dead end above was looking in the wrong place: `PUT_PERSON_IN_DT` doesn't ride along inside
  `ATTACK`'s per-person sweep, it's its own dedicated `interpret_script` opcode (id 1097, case `0x48d22b`, bounded
  exactly between the already-known `PRAY_AT_HEAD`/`I_HAVE_ONE_SHOT` cases). Traced the full chain: the opcode
  case calls `0x4925e0` (resolves the 3 `model x z` operands) which calls `0x4e67b0` - **one of the SAME ~21
  "AI goal evaluator" functions `ATTACK`'s own `0x4e5fd0` belongs to**, called directly from the script opcode
  rather than from one of `maybe_ai_func_1`'s priority-template slots. `0x4e67b0`: claims a free AI task slot
  (silently does nothing if none free), resolves `(x,z)` to THIS tribe's own nearby class-2/type-4 "tower"
  building via a small-area search (`0x4f33d0`, own row - silently does nothing if no tower is nearby), checks
  the tower isn't already garrisoned by `model`'s type or a shaman (silently does nothing if so), then enqueues
  **task 7** (`0x4c8910`, already fully traced, previously only a "candidate" link - now CONFIRMED) with
  `param_a`=the tower's id, `param_b`=`model`. Task 7 then does the actual work it was already known to do:
  evicts any wrong-type non-shaman occupant, finds and recruits the nearest eligible unit of `model`'s type near
  the tower, commits it to person state 14, and finalizes. **Net: `PUT_PERSON_IN_DT model x z` doesn't teleport
  a specific follower into a tower - it kicks off an async "evict wrong type, then walk the nearest eligible
  `model`-type follower in" task against whichever of the tribe's own towers is nearest `(x,z)`, failing silently
  (no script-visible error) if there's no free task slot, no nearby tower, or the tower is already correctly
  staffed.** Full write-up: `docs/functions.tsv` rows `0x48d22b`/`0x4925e0`/`0x4e67b0`/`0x4f33d0` (new/updated),
  `0x4c8910` (updated to drop the "candidate" hedge).
- **RESOLVED this session: task 2 is the shaman's own autonomous "seek wildmen, cast Convert" behaviour, not
  ghost-escort management.** Fully traced its 9-state dispatch (`0x4c7a3c`): states 0-7 walk her toward a
  base-adjacent target (several position sources, a computed fallback, a claim/commit step); state 8, the task's
  real long-lived steady state, does a cheap 4-neighbour hill-climb each tick (via a newly-identified wildman
  census function, `0x4f79d0`) to drift the target toward the nearest small pocket of wildmen, then - once in
  range and off cooldown - casts spell 17 (Convert, confirmed via `open-populous3`'s own spell-id table) there
  using the EXACT SAME readiness/mana/cast primitives the scripted auto-cast task (`0x4c9580`/`SET_SPELL_ENTRY`)
  and `ATTACK`'s own shaman branch (`0x4cc553`) already use. The "reset a linked follower" block from the prior
  session's partial read turned out to be a one-shot "release whatever's currently attached to me" cleanup
  (`shaman+0x9f`, a generic back-reference, not specifically a ghost) that always ends the task once triggered,
  not an ongoing escort loop. Full write-up: `docs/functions.tsv` row `0x4c7370` (rewritten), `0x4f79d0`
  (corrected from a guessed height-function to a confirmed wildman census), `0x4c2e00` (new).
- **RESOLVED this session, with a correction partway through: task 19 is a VEHICLE mission-readiness/loading
  task (boat or balloon), not a population/building-capacity expansion decision as this same session first
  concluded.** All 13 states of `0x4caac0`'s own dispatch now read. The first pass (reflected in an earlier
  draft of this entry) mis-read the task's own "type 3/4" branch as "hut big"/"tower" building types, because
  `+0x16`'s resolved record and the literal byte values 1-4 happen to collide with class-2 (building) type ids -
  re-tracing `0x4f77e0` (the count function) directly settled it: it walks the GLOBAL object list filtering
  CLASS 4 (**vehicle**, `docs/unit_types`), not class 2 (building). So `+0x16` is a VEHICLE throughout, found by
  `0x4f92b0` via a person already linked to it (a crew member/pilot) with room to spare; type 3/4 = "air 1"/"air
  2" (**balloon**), the else branch = "boat 1"/"boat 2" (**boat**) - not hut-big/tower at all. With that fixed,
  the whole task reads as: maintain enough ready, crewed boats/balloons for the difficulty level (counted via
  `0x4f77e0`); for a balloon short of target, find a nearby vehicle-free staging cell (`0x4cec10`'s validated
  3x3 grid - itself confirmed vehicle-specific, since its own validity checks `0x4650d0`/`0x465440` explicitly
  reject any cell occupied by another class-4 object) and claim the balloon; for a boat, find the tribe's boat
  hut and compute its water-exit launch point; either way, once the vehicle still has room and is still needed,
  **load its crew/passenger slots** (`+0x7a`, a small array sized by a per-vehicle-type capacity table,
  `0x5a7940`) by committing each one to person state 14 - the same generic "committed" marker every other task's
  worker-assignment uses, here meaning "boarding." **Not found this session**: this task does not itself issue
  an `ATTACK`/task-20 order - it manages vehicle readiness and loading only; departure/attack presumably comes
  from a script's own `ATTACK ... ATTACK_BY_BOAT`/`ATTACK_BY_BALLOON` call consuming an already-loaded vehicle,
  not traced from this side. Full write-up: `docs/functions.tsv` row `0x4caac0` (rewritten a second time),
  `0x4f77e0`/`0x4f92b0` (corrected from building- to vehicle-counting), `0x4cec10`/`0x4650d0`/`0x465440`
  (confirmed vehicle-exclusivity checks), `0x465650`/`0x4f3b20` (re-confirmed as vehicle-site checks in practice
  despite being written generically).
  **RESOLVED, a later session: `0x4f2d40` traced, and the "vehicle loaded -> vehicle departs" hand-off confirmed
  absent from this task - both of this item's own open ends now closed.** `0x4f2d40` (`fn(pos, &out, radius) ->
  bool`, own `functions.tsv` row) turns out to be an unrelated notification-positioning helper, not any kind of
  order/movement primitive: it scans a `radius`-sized grid of cells around a candidate position for the first one
  whose terrain is WATER (table `0x5aa328` bit `0x2`), used here (and, confirmed by the same session, in tasks
  17/18 too) ONLY to refine the boat-hut's coarse facing-derived exit guess (`+0x12`) into a real nearby water
  cell (`+0x1e`), fed straight into `0x435730`'s own category-3 "commit/refocus" notification broadcast - never
  into a destination/order field. So the hand-off question is answered in the negative, not left open: task 19
  genuinely never sets a vehicle moving or enqueues an attack, full stop. The actual hand-off was separately
  found (by an even later session, before this correction was written back here) to live entirely in `ATTACK`'s
  own task-20 vehicle sub-state-machine (`0x4cceb0`, own `functions.tsv` row) - it independently re-checks vehicle
  stock, crews/boards the specific vehicle(s) a given attack needs, and sets them moving itself (its own state 7,
  via `0x4d14f0`); tasks 19/27 never call into it and it never calls back into them (confirmed: no reference to
  `0x4f2d40`, or to tasks 19/27's own code, anywhere in its body - it re-derives the boat's water-exit point with
  its own separate, stricter inline check instead of sharing `0x4f2d40` or any of task 19's tables, correcting
  that row's own earlier "the SAME search" wording). Full write-up: `docs/functions.tsv` rows `0x4f2d40` (fully
  rewritten), `0x4caac0`/`0x4cceb0`/`0x4c9bf0` (updated).
- **RESOLVED this session: task 27 fully traced, confirming a user hypothesis in substance ("board units into a
  vehicle, use/manage the vehicle, disembark") with one correction (it is FIREWARRIOR-specific, and it does not
  move a mis-parked vehicle).** All 11 states of `0x4cf970`'s own dispatch now read. State 0 checks the tribe can
  afford a vehicle-model's worth of transport for a requested headcount (ceiling-divided by that model's own
  passenger capacity) against a per-tribe-per-model count (`tribe+0xba5`, not independently confirmed). State 2
  (huge) runs two global CLASS-4 (vehicle) scans: one validates every occupant of already-loaded, ready vehicles
  and "selects" the fully-valid ones; the other checks whether a ready vehicle is validly parked - if so, finds
  its disembark point and unloads its passengers one at a time (`disembark_vehicle`/`0x4659d0`, already a
  confirmed function); if NOT validly parked but already half-loaded, it's selected anyway but **no movement
  order was found for it** - this is the one part of the hypothesis NOT confirmed, a vehicle short of a valid
  resting spot is left alone by this task, not redirected. State 4 then recruits troops to fill the needed
  headcount via the shared proximity worker-finder with `type_lo=type_hi=6` - **explicitly firewarriors**,
  settling the task's own "firewarrior-specific" character the prior session's partial read had only guessed at.
  States 5-9 poll for readiness, do a final pilot-commit pass, and broadcast finalize notifications; state 10
  cleans up by de-selecting any vehicles this task marked. **Not found**: an `ATTACK`/task-20 enqueue, matching
  task 19's own same gap - this task manages vehicle readiness/loading/disembarking only, not departure/attack
  itself. Full write-up: `docs/functions.tsv` row `0x4cf970` (fully rewritten), `0x4f2460`/`0x4f24c0` (corrected/
  updated), `0x4f24a0`/`0x4f24d0`/`0x4f2520`/`0x4d1d90`/`0x4d21e0` (new, named but not traced).
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
- **RESOLVED this session: `ATTACK`'s vehicle-transport sub-machine (`0x4cceb0`) traced through to the actual
  attack dispatch, closing the loop between tasks 19/27 (fleet maintenance) and combat.** Following up on the
  session's own earlier "code 6" find: state 0 checks vehicle stock (already documented); **state 2** crews the
  specific vehicles needed for this attack - disembarking invalid occupants from partly-loaded ones, and for
  empty ones, finding the nearest brave and ordering it to board (order kind `0x16`/`0x43ba10`, whose handler
  reads the target's own vehicle-attachment field - plausibly a dual-purpose "attack or board" order kind,
  gated by target class, not fully disambiguated); **state 7** calls `0x4d14f0` - now confirmed (a second call
  site found) as the generic "set the gathered force/vehicle moving as a group" primitive, the SAME function
  `ATTACK`'s own land-based substate 6 calls - this is the literal "the loaded vehicle departs" moment; **state
  17**, reached after an (unread) arrival-poll loop, calls `0x4ce2c0` - **the identical per-person attack-order
  sweep `ATTACK`'s own land-based substate 17 uses** - confirming a vehicle-borne force attacks through the exact
  same shared mechanism as a land-based one, not a separate path. **Addendum, prompted by a user question asking
  whether code 52 means "cancel the mission" - checked directly and the answer sharpens both codes' meaning.**
  `0x33`(51) IS a genuine cancellation: `0x4ce2c0` found nothing left capable of attacking, so no attack ever
  goes out. `0x34`(52) is reported AFTER `0x4ce2c0` already succeeded (the attack DID fire) - it's a one-shot
  "nudge any remaining stragglers, gated by a time/cycle cap and a regroup-quota check" tail that always runs
  once then ends the task regardless of outcome - so 52 reads as "attacked, but the final regroup nudge hit its
  own cap," a timeout/partial-success marker, not a cancel. Chasing this also surfaced the function's own true
  terminal state (18, not just the bare `0x4ce020` sentinel): it de-selects marked vehicles (same sweep task 27's
  own cleanup uses), then writes a 5TH, generic fallback code (`5`, "mission ended") via a new gate function
  (`0x48c680`) - but ONLY if nothing more specific (6/51/52) was already reported this run. **Net, closing the
  whole lifecycle**: tasks 19/27 keep a fleet stocked/crewed ahead of time; `ATTACK` re-checks stock, crews the
  specific vehicles needed, sets them moving, and on arrival issues the same combat orders a land attack would,
  ending in one of 4 now-documented outcome codes (5 generic, 6 no vehicles, 51 cancelled on arrival, 52 attacked
  but regroup timed out) on top of `0x4E5FD0`'s own original 0-3. Full write-up: `docs/functions.tsv` row
  `0x4cceb0` (substantially extended), `0x48c650` (all 5 codes consolidated), `0x48c680` (new),
  `0x4d14f0`/`0x43ba10` (corrected/extended), `0x4f3af0`/`0x4f3b10`/`0x4f5950` (new, named but not traced).

## Combat

- **RESOLVED this session: `0x416D70`, the watchtower sentry's own "visibility/LOS test," is not a line-of-sight
  check at all.** Fully read (21 instructions): it's the canonical standalone tribe-relations/diplomacy gate
  (tribe==0xFF / tribe==tribe / diplomacy bitmask `0x9608B6`) that several other combat functions
  (`0x51EAB0`/`0x51C4C0`/`0x43ABF0`/`0x51D0B0`) had each independently hand-inlined - no position, terrain or
  obstruction read anywhere in it. The watchtower sentry scan (`0x40BD20`) only ever decides to "alert" based on
  tribe/diplomacy, the same as every other combat eligibility scan in the exe - there is no separate geometric
  line-of-sight mechanism for towers. Full write-up: `docs/functions.tsv` row `0x416d70` (also corrected
  `0x40BD20`'s own stale "LOS/visibility check" label to match). Two of its 6 call sites (`0x408ED0`, `0x514410`)
  were only read as far as this one call and remain open leads of their own if a future session wants the rest
  of their scans (melee-adjacent filter, and an AoE damage scan respectively).
- **Follow-up, same session: `0x408ED0` fully traced - and `0x40BD20` turns out NOT to be an autonomous sentry
  after all.** `0x408ED0` (`docs/functions.tsv`, new row) is the per-turn, every-building re-check that silences
  an already-active "alerted" flag (`+0x9C` bit `0x10`) once no enemy remains near the building's own doorway
  cells - not a detector, a "stand-down" check. Re-reading `0x40BD20`'s own existing write-up alongside it
  surfaced a bigger correction already on record there but worth restating: `0x40BD20` isn't a per-turn
  autonomous watch either - it's the handler for the player's own "B" rally hotkey (and the rare `CALL_TO_ARMS`
  script opcode), invoked through `0x40BCE0`'s worklist walk, not `unit_processing_class_2_bldg`. **So the actual
  autonomous first-detection trigger that sets `+0x9C` bit `0x10` in the first place is still unlocated** - a
  concrete, well-scoped next step: search for writers of that bit (building `+0x9C`, word field) elsewhere in the
  exe.
- **RESOLVED, later session (2026-11-07): the "still unlocated" writer found, and it overturns the "autonomous
  sentry" framing entirely - there is no detection radius or LOS scan involved at all.** A full-exe search for
  `[reg+0x9c],0x10` writes (not just reads) in `dis.txt` turned up exactly one: a trivial 2-instruction setter at
  `0x40BAE0` (`building_set_alerted`, new `docs/functions.tsv` row) - `building+0x9c |= 0x10`, nothing else, no
  caller-side gating of its own. Its only 5 call sites are all inside `attack_order_handler`/`0x51A2A0`'s
  building-target (class-2) sub-state machine (pinned down at `0x51B0E7` in an earlier session), one per
  "hit" sub-state, each immediately after that sub-state's own `0x407810(building,6)` "shake the building" call.
  **So the real trigger is "a unit just landed a melee hit on this building," full stop** - no occupancy check,
  no garrison-type check, no tower-type check, no DT_RADIUS-scaled range: the only preconditions are the ones
  `attack_order_handler` already enforces to reach that branch at all (target is class 2/any building, target's
  tribe differs from the attacker's). The player-reported "tower alarm (song + notification) when a manned tower
  spots an enemy at range, scaled by elevation" conflates two genuinely separate mechanisms that happen to share
  one downstream consumer (`0x89D167`'s "fight involving you" flag, per `0x40BD20`'s own write-up): (1) this
  bit/`0x408ED0`'s sound-0x34 siren, which is a generic "any of my buildings is currently being melee-attacked"
  alarm with zero range component, not tower- or garrison-specific; (2) the DT_RADIUS-scaled detection radius
  (`0x40B450`/`0x40BD20`) is real but belongs to the unrelated, player-hotkey-only "B" rally command, confirmed
  in an earlier session to never run autonomously. Also found, not yet traced: `0x40BAE0`'s paired getter
  `0x40BAC0`/`building_is_alerted` has 2 call sites (`0x471129`, `0x472494`) that look like render-reveal checks
  for normally-hidden enemy objects - a plausible lead for the notification/reveal half of the alarm, left open
  for a future session (own `functions.tsv` row has the detail).
- **FOUND, later session (2026-11-07): a THIRD, genuinely autonomous combat mechanism, separate from both of the
  above - the player's own "self-defense" report (a firewarrior garrisoned in a building throws fire at a nearby
  enemy without leaving; a garrisoned warrior walks out to fight one on its own, neither via the B hotkey or the
  building-attack alarm).** Traced the issuer of order kind `0x15`/21 ("attack, self-issued auto-scan" in the
  `order_execute`/`0x432D18` catalog, previously unlocated): `0x4D4690` (own `functions.tsv` row, already known
  to run for every owned person every eligible tick from earlier Preacher-conversion tracing) dispatches by
  person type - preacher/shaman to `preacher_auto_scan`/`0x51E7B0`, firewarrior (gated by a trivial check,
  `0x51FCD0`) to its own dedicated scan `0x51E9A0` (new row), everything else to the generic melee scan
  `0x51E5E0`/`0x51EAB0` - with a GHOST-status override (`self+0x11` bit `0x8`) to a parallel scanner `0x51E6F0`
  (new row) regardless of type. **Confirmed by reading `0x51E9A0`'s own code**: the firewarrior's scan reads its
  OWN CURRENT cell (`+0x3D`/`+0x3F`) as the scan centre - it does not walk anywhere first, consistent with its
  ranged nature (`firewarrior_fire`/`0x51FBF0`) - and **nothing anywhere in this whole dispatch chain
  (`0x4D4690`, `0x51E5E0`, `0x51E7B0`, `0x51E9A0`) checks whether the unit is currently a building occupant**
  (the `+0x86` array) before running. Also confirmed the call site feeding `0x4D4690` (inside the generic
  per-person per-turn tick, `~0x4D3B3F`) only excludes units with no tribe (`+0x2F==0xFF`, i.e. wildmen/neutral) -
  no occupancy/garrison exclusion there either. **Net reading (not live-verified this session): this is one
  single autonomous "if I can see an enemy from where I am, attack it" mechanism that produces two different
  VISIBLE outcomes purely because of each type's own engagement range** - a ranged firewarrior can satisfy its
  self-issued attack order from wherever it currently stands (even a building's doorway cell, so it fires
  without leaving), while a melee type (warrior, generic scan) needs `attack_order_handler`'s own
  approach/arrival sub-states to physically close distance first, which - if it started inside a building -
  means walking out through the door before it can land a hit. Two outcomes, one mechanism, no building-specific
  code anywhere in the chain. **All four of this entry's own "open leads" resolved, later session (static only,
  no Wine/game data available in that container).** `0x51F470` (firewarrior candidate search) and `0x51EE10`
  (ghost-path candidate search) both fully traced: same square-area per-cell scan skeleton and tribe/diplomacy/
  hostility gate (reusing `0x4DE7B0`, the SAME helper `0x40BD20`'s watchtower scan uses - not sentry-specific),
  but `0x51EE10`'s own candidate filter is narrower (ghost-or-shaman-only, plus a `+0x9d==0`/per-state-table
  check) - a ghosted unit's auto-defense targets other ghosts or enemy shamans specifically, not any nearby
  enemy. `0x51F470` turned out to be a GENERIC helper, not firewarrior-exclusive: a second confirmed caller
  (`0x5028D5`, inside the `guard_control_units` per-turn walk's "any class-10 controller type other than
  6/FORMATION" branch) runs a controller object through the exact same person-targeting eligibility matrix -
  which controller type this is, and what it does with the result, is a new open lead. `0x51F470`'s own two
  result codes (previously "plausibly building vs. person, not confirmed") are now resolved: code `2` is an
  ordinary person hit; code `3` is a confirmed SEPARATE "alternate target slot of this cell" hit via a new
  helper (`0x4BAAB0`, own `functions.tsv` row), through a different per-cell table field than the person-chain
  - supporting, not just hypothesizing, the building-target reading. `0x520480` fully traced: it's genuine
  same-cell deduplication - when self (or any unit) shares its EXACT cell with another unit of the same type/
  tribe/state/cached-order-kind (further requiring BOTH ghost-flagged if self is), it hands that other unit the
  SAME order group and marks it "already acted," so a ghost and its still-living original (the most plausible
  real-world case of two units sharing a cell) attack together from one scan rather than duplicating it - not
  building-eviction, as suspected, and not live-verified whether that same-cell case ever truly occurs.
  **Order kind `0x22` is RESOLVED, not just "not yet traced": `order_execute`'s own bounds check
  (`sub eax,3; cmp eax,0x1E; ja default`) puts `0x22`(34) outside the table's kinds-3-33 range entirely
  (`34-3=31>30`), so it falls to the same silent "no handler, never completes" path as any invalid kind - a
  firewarrior's "alternate target slot" self-issued order is permanently inert once issued, never actually
  attacking anything.** `0x51FCD0`'s own gate (`unit+0xB2==1`) is still not conclusively explained, but a new
  data point was found: `0x43A4D0` (the disguise/infiltration order) tests the SAME `+0xB2` offset as a
  multi-bit flags byte (bits `0x1`/`0x2`) on a DIFFERENT unit type, confirming the offset is reused for at
  least 3 unrelated purposes across unit types (spy disguise flags, this firewarrior check, and the Angel of
  Death's own kill-count byte) - whether the firewarrior's reading is "bit 0 of a shared flags byte" or a wholly
  separate reuse remains open. No live memory check was run (none available in that container either) to confirm
  a garrisoned firewarrior's position fields really do read as "at the doorway" while inside - still open if
  this needs stronger confirmation before going into a reimplementation spec. Full write-up:
  `docs/functions.tsv` rows `0x51f470`/`0x51ee10`/`0x520480`/`0x51fcd0`/`0x4baab0` (new)/`0x432d18` (kind 0x22
  addendum).

## Notifications

- **The building-alert "song + notification" has (at least) two genuinely separate halves, and only one of them
  was found to actually do anything - the other may be dead code.** Picking up on `0x409140`/`0x409200`'s own
  already-documented but unexplored tail (writes a camera-alert position `0x89C6E5` and ORs `0x89DB05` bit
  `0x8000`, gated to the LOCAL PLAYER's own buildings only, debounced by a one-shot gate `0x89CE60`): (1)
  **the audible siren is real and already fully traced** - `0x408ED0` plays sound `0x34` on a double-gated roll
  for ANY alerted building regardless of tribe (prior session, see "Combat" above) - this part needs no further
  work. (2) **the camera-jump/banner half could not be confirmed to do anything.** A third writer of the
  identical `0x89C6E5`/bit-`0x8000` pair was found this session, inside `main_loop_inner`/`0x4EC6F0` (own
  `functions.tsv` row) - a generic "a fight involving you is happening somewhere" sweep over a not-yet-identified
  active-fight list (`0x890358`, own row, open), separate from the building-specific writers, confirming this
  notification channel is meant to be a general "something combat-related needs your attention, look here"
  signal, not building-exclusive. But an exhaustive search of every instruction form that could read bit `0x8000`
  of `0x89DB05`, or read `0x89C6E5` at all, anywhere in `dis.txt` found **zero consumers** - every other bit in
  the same per-tribe dword has a reader (mostly the level-script condition-check cluster around `0x48D8xx`), just
  not this one. The debounce gate itself (`0x89CE60`) looks like it resets every turn (traced to `0x4EC785`
  inside `main_loop_inner`, reusing a register from an unrelated adjacent per-turn stats write - not confirmed
  with full certainty it's always 0 there), so this isn't a "fires once ever" oddity explaining the missing
  reader either. **Confirmed-not-done this session**: finding the "Space" keybind (shortcuts.md: "camera to the
  tower under attack") in `process_cmd`'s own `ui_cmd` dispatch table, which would settle this definitively one
  way or the other - either it reads `0x89C6E5`/bit `0x8000` (missed by this search, e.g. via an addressing
  pattern not covered, or an indirect/pointer-based access) confirming the mechanism is real and just rarely
  exercised, or it reads something else entirely (e.g. `0x895DBB`'s own HUD-widget struct, which `0x89D167`
  already writes - "Combat" above, `0x4ECA2D`'s row) and this whole `0x89C6E5` pair genuinely never got wired up
  in the shipped game. **Concrete next step**: locate Space's `ui_cmd` case the same way B/`0xBF` (CALL_TO_ARMS)
  was found - grep `backup.xml`'s own `switchD_<addr>::caseD_<id>` symbols for `process_cmd`'s main dispatch
  table (`0x4AD814`/`0x4AD8DC`, per commands.tsv) for whichever case reads either global, and read it end to end.
- **User correction, later session: the icon-click camera-jump and the "Space" bell alarm are two SEPARATE
  systems, not one with a missing reader.** The clickable notification stack (building/fight under attack,
  preacher conversion in progress, enemy spell cast - all sharing one icon stack with a click-to-camera-jump
  action) is a different, generic multi-event system - most likely the already-identified `fire_advisor_message_
  once`/`0x44D7F0`/`render_land_ui_1` pipeline (pop3-rev-analysis.md "Notifications"), whose CLICK handler
  (as opposed to its per-frame draw, already found) is still unlocated - `render_land_ui_1` (`0x44A2F0`-
  `0x44ABD4`) is the right place to keep looking (it reads/writes the shared record `0x68B6A1`/`0x68C6xx`
  nowhere else in the exe, so any click-detection for it, if present, lives inside this same function). Space
  is explicitly NOT part of that system - it's its own dedicated keybind, separate from the icon stack.
  **This session's attempt to find Space's own binding via `backup.xml`'s `switchD_`/`caseD_` symbols failed**
  (`switchD_004ab6f3`/`004abc0e`/`004adda9` are the only ones Ghidra recognised anywhere near `process_cmd` -
  none of them are the `0x4AD814`/`0x4AD8DC` table B/G use, which Ghidra apparently never recognised as a
  switch at all). **Instead, validated a reusable, much faster alternative this session: reading the remap+jump
  tables' raw bytes directly out of the exe file** (`.text` VMA `0x401000` -> file offset `0x400`, a plain
  Python `struct.unpack_from` one-liner) rather than hand-decoding the disassembly - confirmed correct by
  reproducing `ui_cmd 0xBF`/`0xC1`'s own already-known handler addresses (`0x4AD2BC`/`0x4AD318`) exactly from
  the raw table bytes. **Also discovered `process_cmd` actually chains TWO such table pairs** (an outer one at
  `0x4AD740`/`0x4AD5C4` whose own cases can fall through into the `0x4AD814`/`0x4AD8DC` pair via a shared tail
  at `0x4ABBE2`, using a DIFFERENT index formula - `raw_id-0xF` - than whatever formula the 0xBF/0xC1 cases use
  to reach the same second table directly; the two formulas were independently verified against known-good
  answers but not yet reconciled with each other) - see `0x4AAB80`'s own corrected `functions.tsv` row for
  the full mechanism. **A promising scancode-shaped lead (DIK_SPACE=0x39, DIK_RETURN=0x1C, DIK_NUMPADENTER=0x9C
  all appearing as literal comparisons inside `0x4A9D90`) turned out to be a false trail**: that function is a
  generic "set/toggle one named OPTION by id" dispatcher (already correctly identified by a prior, unrelated
  session chasing an Angel-of-Death lead), and `0x39` there is just an option id that happens to numerically
  coincide with the DIK_SPACE scancode, not an actual keyboard check - its real callers (who pass it option id
  `0x39`) were not identified. Chasing it anyway all the way through to `ui_cmd 0x5b`'s own handler
  (`0x4ABD86`, now fully traced, own `functions.tsv`/`commands.tsv` rows) found a PAUSE/UI-panel-visibility
  toggle, not an alarm - confirming this was the wrong trail, not an incomplete one. **The real Space/bell-alarm
  binding remains unlocated.** Given how easy it is to find a numerically-plausible but wrong lead in this
  exe's heavily-reused id space, **a live memory check is very likely faster than continuing static analysis
  here**: watch `0x89C6E5`/`0x89DB05` (and, as a cross-check, `0x89D167`/`0x895DBB`) while the user presses
  Space in a real game with an active fight or a building under attack, the same way `scripts/livemem.py` was
  used for the mouse-tracking investigation (`docs/cheat.md` "Docker headless rig") - this would show directly
  which global(s) actually change, if any, cutting out the dispatch-table archaeology entirely.
- **User correction, same thread: `0x4A9D90` genuinely IS a keyboard dispatcher after all - just not for gameplay
  hotkeys. It's the multiplayer chat / BYRNE cheat-code text-entry box's own per-keystroke handler.** Confirmed
  by reading the exe's own static data: `0x4A9D90` and its sibling `0x4AA1C0` (own `functions.tsv` rows) are
  function-pointer fields inside a dialog-descriptor struct at `0x5CDB98`, which also holds seven repeated
  UTF-16 `"%s: %s"` format strings - a chat scrollback entry shape (sender + message), not a settings panel.
  `0x526A80` (own row) is the generic dialog-event pump that invokes the descriptor's own callback - the actual
  reason `0x4A9D90` has zero direct callers anywhere in `dis.txt` (it's only ever reached through this indirect,
  function-pointer path, which is why the prior Angel-of-Death session and this thread's own earlier session
  both mischaracterized it from the disassembly alone). This retroactively validates the DIK-scancode-shaped
  checks inside it: Enter/Numpad-Enter (`0x1C`/`0x9C`) really is keyboard input, reading as "submit the typed
  chat line" (`ui_cmd 0xB0`); a code-`1` case reads as "cancel/close" (`ui_cmd 0x9B`, shared with `0x4AF780`'s
  own dismiss-dialog call to the same id). **Still open**: the Space-shaped case (`esi==0x39`) calls `ui_cmd
  0x5b`/`0x63`, both confirmed elsewhere to be pause/UI-panel toggles - doesn't obviously fit "type a space
  character into a chat message." Working hypothesis, not confirmed: this same per-keystroke callback may be
  shared between ordinary chat AND the separate BYRNE cheat-code entry screen (AGENTS.md's "hold TAB+F11..."
  note), with Space's effect depending on which one is active. **This does NOT answer the original "Space: bell
  alarm" question** - if anything it makes `0x4A9D90` a LESS likely candidate for that keybind now that its real
  purpose (a chat box, only reachable while that dialog is open) is understood; the live-memory check recommended
  above remains the fastest way to find the real one.
- **RESOLVED, same thread, without any live check: "the chat should have icons for which tribe to send to"
  (user recollection) - confirmed true, found end to end via the exe's own import table and strings, not by
  running the game.** With no Wine/display available in this environment to do the live check the prior entry
  recommended, searched `strings`/`objdump -x` for anything chat/network-shaped instead: found a real, demangled
  C++ import, `?SendChat@MLDPlay@@QAEHKPAGKPAK@Z` = `int MLDPlay::SendChat(unsigned long dest, unsigned short*
  text, unsigned long, unsigned long*)`, imported from `weanetr.dll` (the game's DirectPlay-style multiplayer
  library). Resolved its IAT slot with `pefile` (`0xD0C9B8`, own `functions.tsv` row) and found 4 call sites;
  the one inside the chat-send function (`0x4AE5B0`, own row) is a clean, self-contained answer: a 4-byte array
  `0x96AAB6`-`0x96AAB9` holds one "selected as recipient" flag per UI slot - slots 0-2 for the 3 tribes other
  than the local player (via an index-remap helper, `0x4A25B0`, own row, "the Nth tribe other than me"), slot 3
  a dedicated "ALL" flag. If nothing is explicitly selected, or ALL is set, one broadcast `SendChat(0xFFFFFFFF,
  ...)` goes out; otherwise one `SendChat` call per individually-selected tribe. The icon click/toggle handler
  itself (`0x49EB50`, own row, found via the same array) has real UI logic matching a typical radio-adjacent
  multi-select: toggling an individual tribe auto-syncs the ALL flag (set if all 3 end up selected, cleared
  otherwise) and refuses to let you deselect your way down to zero recipients (forces the last one back on).
  **Net: exactly the mechanism the user described** - per-tribe recipient icons plus an "everyone" option,
  controlling the destination of each `SendChat` call. Still open, lower priority: which on-screen widget/icon
  list actually owns the `0x49EB50` callback (not the same descriptor as the chat text box itself, `0x5CDB98`,
  which has no spare callback slot for it) and the other 3 `SendChat` call sites (`0x40F593`/`0x40FC2B`/`0x45438D`)
  not yet traced. **Methodological note for the next "we can't run the game" situation**: `strings -e l` (UTF-16)
  plus `objdump -x`'s import table, and demangling of any `?Name@Class@@...` C++ symbols found there, turned out
  to be a far faster and more conclusive path than guessing from UI code alone - worth trying BEFORE spending a
  long session on disassembly archaeology whenever the question smells like "what does clicking X actually DO"
  (network sends, file I/O, and other externally-visible actions are exactly the kind of thing that shows up as
  a named import, even when the UI code that triggers them is deeply indirect/callback-based).

- **Attempted the recommended live-memory check, later session (2026-11-08) - initially looked like a NEW, more
  fundamental blocker than "mouse doesn't work" (ordinary gameplay hotkeys not reaching the game at all), but a
  user correction resolved it: it's a focus problem, not a broken input path.** Full method in `docs/cheat.md`
  ("`process_cmd` breakpoint method..."): a GDB breakpoint on `process_cmd`'s own `ui_cmd` argument load
  (`0x4AABA1`, fires on EVERY call regardless of id - a strictly better probe than guessing which global a handler
  might write) caught **Escape live, `ebx=0x9b`**, confirming `commands.tsv`'s own row for that id, but `b`/
  `space`/`g` initially produced zero hits. Once the game window was kept actively focused (not just activated
  once beforehand - something between test runs, e.g. a screenshot command, was stealing it back), `b` reliably
  produced **`ebx=0xbf`** (confirming the long-standing static guess for the "B: help the tower" keybind for the
  first time live) and - during one interleaved b/space run - a single hit of **`ebx=0x59`**, a previously
  uncatalogued id. Delivery remained flaky even with focus held (likely genuine X11 synthetic-event drop, matching
  this repo's older "`xdotool key Down`/`Up`... silently drops roughly a third to half of presses" note) - `0x59`
  was not reproduced in ~9 further isolated single-key attempts of either key, but `b` was also never seen to
  produce `0x59` across 11 attempts (always `0xbf` or nothing), making `space` the more parsimonious source.
  **RESOLVED (probable, not 100% certain): `ui_cmd 0x59` is very likely Space's own binding, and it is NOT a pause
  toggle or a dead end this time - it's a genuine, complete "jump camera to the current combat alert" mechanism,
  traced end to end statically after the live hit pointed at it.** Three new pieces, none previously catalogued:
  `0x4DA2A0` (runs every tick for every owned person, alongside the already-known self-defense auto-scan call
  cluster at `~0x4D3B3F`) detects a hostile sharing the person's own cell and STAGES an alert - the hostile's
  pointer into `0x8922DC`, a 96-turn TTL into `0x89C6A5`, and the THREATENED PERSON'S OWN cell into `0x89C6A1`;
  `0x4F0E00` (called every turn from `main_loop_inner`, right alongside the already-documented `0x89D167`/
  `0x890358` fight-notification writes) validates/expires that record and, while it's live, plays **sound `0x23`**
  on a periodic pulse (4x/32 turns if visible to the local player, 1x/32 turns if not) - very plausibly the
  audible "under attack" alarm itself; and `0x4ABD0D` (`process_cmd`'s own `ui_cmd 0x59` handler) consumes
  `0x89C6A1` and feeds it through a newly-traced camera-recenter pipeline (`0x417CA0`/`0x417D80`, which writes a
  camera-focus position into `0x89C6E3` - immediately ADJACENT to, and plausibly the missing other half of, the
  long-dead-ended `0x89C6E5` "camera-alert position" global from the ORIGINAL Space investigation, which searched
  for readers of `0x89C6E5` itself and found none - the off-by-one-field address may be why). Full write-up in
  `docs/functions.tsv` (`0x4da2a0`/`0x4f0e00`/`0x417ca0`/`0x417d80`/`0x4abd0d`) and `docs/commands.tsv` (`ui_cmd
  0x59`). **Still open**: confirm the key binding beyond one ambiguous live hit (a cleaner reproduction - ideally
  triggering a real in-game attack so the alert is actually pending, then pressing Space and watching `0x89C6A1`
  flip to `-1` and the camera move, would settle it definitively); the role of the second linked object `0x8922E0`
  `0x4F0E00` also validates; and what `0x478820`/`0x449080` (minor calls in this same chain) actually do. **Also
  logged as an operational hazard, not specific to this investigation**: letting a GDB session attached to this
  exe die uncleanly (`SIGKILL`/timeout instead of a real detach) leaves its software breakpoint's `0xCC` byte
  stuck in the tracee's memory, crashing the game the next time anything executes that address - this happened
  three times this session (twice from an unclean timeout, once for an undiagnosed reason after a clean detach) -
  see `docs/cheat.md`'s own write-up for the restore-byte workaround, needed every time.

- **RESOLVED, later session: which class-10 controller type reaches `0x51F470` via `0x5028B0`'s "anything else"
  branch - the previous session's own open lead from the combat self-defense tracing above.** It's type `0xA`
  ("guard control" per `docs/unit_types`), NOT a FORMATION (type 6) controller as the branch structure there
  might suggest. Confirmed via `0x4ECAC0`'s own per-turn object-classification pass (Ghidra's `init_tribe_struct`
  - a likely misnomer, confirmed to run every turn from `main_loop_inner`/`0x4EC942`, not once at level load):
  its class-10 sub-dispatch (table `0x4ED4F4`, types 1-13) pushes type `0xA` specifically onto
  `guard_control_units` (`0x890360`); type 6/FORMATION controllers go onto a different, unidentified list
  entirely. The SAME classification pass also confirmed `fight_units`(`0x890358`)/`pre_fight_units`(`0x89035C`)
  are built from controller types 8/9 (matching `docs/unit_types`' own naming exactly), and that
  `guard_control_units` ALSO receives effect type `0x5A` ("atlantis invoke" - unidentified, plausibly unused/cut
  content) and shot type `6` (not in `docs/unit_types`' own shot list at all) - so the list is a genuine mixed
  bag by design. The guard-control coordinator's own init (`0x5027E0`, new `functions.tsv` row) was also traced:
  it's a stationary sentry planted at a fixed world position (decoded from a scan-centre cell word) with a FIXED
  6-cell scan radius, running `0x51F470`'s person-targeting eligibility scan every other tick - **plausibly the
  actual "manned structure detects a nearby enemy at range" mechanism earlier sessions looked for and didn't find
  while tracing the watchtower alert bit (`0x40BD20`) and the building-hit alarm (`0x40BAE0`), both confirmed to
  have NO range component of their own.** Correction to an earlier session's framing: the scratch stack
  `0x892443` (which the guard-control init also pops from) is NOT position-job-specific - re-confirmed this
  session as a pervasively reused generic argument-scratch area used by unrelated functions exe-wide
  (`init_unit_building`/`0x403676` among them); isolate by immediate caller context, don't trust a bare search for
  all its touches. **Two concrete open leads for a future session**: (1) what allocates a type-`0xA` guard-control
  object in the first place (which building type or script action spawns a guard post sentry) - not found, the
  277-touch scratch-stack search above was abandoned as too unfocused; (2) what reads/consumes the scan result
  this coordinator stores in its own `+0x78` on a later tick - i.e. what it actually DOES once it finds a
  hostile (raise the watchtower-style alert? issue an attack order? something else?) - not traced. Full write-up:
  `docs/functions.tsv` rows `0x51f470`/`0x5028b0`/`0x4ecac0`/`0x5027e0` (new).

- **CORRECTED, later session: the "stationary sentry" framing just above is wrong - type `0xA` is the "join/hold
  a melee ring" (order kind `0xB`/11) companion object `0x519F10`'s own row already named as "a THIRD
  combat-adjacent controller type... a genuinely separate 'ring' object", not an unrelated guard post.** Both of
  this item's own open leads are now resolved. (1) **Allocator**: exactly 2 call sites in the whole exe create a
  type-`0xA` controller, `0x519F10`'s own sub-state-0 path and a second, redundant site inside `0x432DF0`'s own
  body (much bigger than its previously-documented opening bit-copy segment, own extended `functions.tsv` row) -
  BOTH reached only for order kind 11, never from a building or script action. (2) **`+0x78` consumer**:
  `0x519F10`'s own per-tick dispatch checks it before its normal sub-state switch - a nonzero result (the
  periodic `0x51F470` scan found something) resets a non-ready ring member's own sub-state back to 0, forcing it
  to re-run `attack_order_handler` - i.e. the scan lets an ongoing melee ring re-engage a new or moved target,
  not detect an approaching enemy from a fixed watch position (this companion has no fixed position at all - it's
  anchored at wherever the ring's own target currently is). Side note: since this companion's own type (`0xA`)
  doesn't match `0x51F470`'s self-type matrix (4/6/8), its ordinary person-hit result (`2`) can in practice only
  ever report an Angel of Death - its real value almost certainly comes from result `3` (the `0x4BAAB0`
  alternate-slot hit instead, which bypasses that matrix). Full write-up: `docs/functions.tsv` rows
  `0x51f470`/`0x5028b0`/`0x5027e0`/`0x432df0` (all re-corrected/extended).

## Spy disguise and infiltration

Traced this session purely from a static `D3DPOPTB.EXE` (a cloud session - no `game/constant.dat`, no Wine, no
`livemem.py`, no way to run the game at all, only the disassembly/consts.txt route): the disguise-application
primitive (`0x4DE760`, writes the apparent-tribe byte + the exe's own named constant `SPY_DISGUISE_DELAY`=63) and
order kind 15's handler (`0x439D30`), a full approach/aim/throw-firebrand/ignite-building/discovery-roll/withdraw
sequence, issued in every confirmed case from the native AI's own spy-only dispatch branch (`0x4CE2C0`). Also
corrected `0x4D6F90`, a previous session's misattributed "disguise issuer" (it's person state 17's unrelated
on-enter handler). Full write-up: `docs/functions.tsv` rows `0x439c30`/`0x439d30`/`0x4de740`/`0x4de760`/`0x4d6f90`
(corrected)/`0x43a4d0`/`0x43b8e0`/`0x4ce2c0` (addenda), `docs/person_states.tsv` row 17. Everything below needs
either a live memory session (an agent with Wine/the running game, or the user's own measurement) or a future
static pass with `game/constant.dat` present - **not done this session, left open on purpose**:

- **Live values for every table this session could only read the FORMULA/shape of.** `0x439D30` substate 2's
  firebrand windup delay reads `*0x59DF44` - a POINTER variable that is zero in the static image (populated at
  runtime, presumably from a loaded resource file) - so neither it nor the paired `0x5A6AFB` table's real
  per-object numbers could be confirmed; same for the discovery-roll threshold table `0x960812` and the
  per-tribe "already alerted" latch `0x89DDE7`/relation byte `0x89DDEA` substate 4 reads. A live session should
  read these the way `livemem.py`/a debugger would, ideally cross-checked against an actual in-game timed
  infiltration attempt (stopwatch the crouch-to-throw windup, the ignite-to-reveal-roll window, count how many
  attempts before being caught at a fixed save/seed).
- **The bottom-6-bits "blink" countdown `0x4DE760` arms (`SPY_DISGUISE_DELAY`=63) has no confirmed consumer.**
  Static search in `dis.txt` for another read of `+0xB2`'s bottom 6 bits outside the handful of flag-bit
  (bits 0/1/2) uses already attributed to `0x43A4D0`/`0x43ABF0` turned up nothing conclusive this session. A
  live session should find what reads this countdown down to 0 - the most likely place is a per-tick visual
  (tint/colour-cycle) or a "can't be targeted as an obvious enemy yet" gate during the transition.
- **The player-facing UI path to order kind 15 (arson) and kind 16 (disguise) was not found.** Every kind-15
  issuer found this session is the AI's own spy branch inside `0x4CE2C0`; kind 16's inline handler (table
  `0x432D18`'s own row) calling `0x4DE760` is a strong candidate for the disguise command, but which `ui_cmd`
  case (a right-click on a tribe's HUD icon with a spy selected, per the user's own description of play) queues
  it was not traced - this needs either a live session (watch `0x438730`'s own order_set call stack while
  performing the click in a debugger) or a dedicated static pass through `process_cmd`'s own dispatch tables the
  way `commands.tsv`'s own method already does for other commands, not attempted this session for lack of time.
- **Whether a player-controlled spy can even reach kind 15 at all.** The AI's own spy branch is reached through
  `maybe_ai_func_1`, the native AI task scheduler - not confirmed whether a human player's spy, given some other
  command, can enter the same order kind, or whether "set building on fire" is purely an AI behaviour the player
  only ever witnesses from the other side (as a target), with the player's OWN in-play arson (per the user's
  report, "I do this with my own spy") going through a different, still-unlocated path.
- **`0x8A03EA`'s own cell-table meaning (0x439C30's "genuine tribemate at the door" scan) wasn't cross-checked
  against the near-identical `0x8A03E4`/`0x8A03EC` slots used elsewhere in this session's own investigation** -
  plausibly the same per-cell "other object list" family at a different byte offset within the same cell record,
  not confirmed.
- **The person-state-21 table `0x89DDE7` (read by both this session's substate-4 discovery roll and the
  already-documented state-21 tick handler, `0x4D3701`) still has no confirmed meaning** - this session's own
  reading ("a per-tribe 'already alerted to infiltrators' latch") is a guess from the one new call site found,
  not independently confirmed; a live session comparing its value before/after a successful vs. failed arson
  attempt against the same tribe would settle it.

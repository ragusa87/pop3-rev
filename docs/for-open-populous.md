# Queue for `open-populous`

This session (and any other pop3-rev session without that repo attached) has no access to
`open-populous`, so none of its findings can be written directly into
`open-populous/docs/specs/pop3-rev-analysis.md` or `open-populous/TODO.md` the way AGENTS.md's
normal pipeline expects. This file is the holding area instead: a future session that DOES have
`open-populous` attached should read it, decide what's actually spec-ready, port it over (spec
write-ups via the `original-game-spec` skill, implementation gaps as `open-populous/TODO.md`
entries), and then trim the corresponding entry from this file.

Nothing below should be copied in verbatim - everything here is still at "named"/un-confirmed
status in `docs/commands.tsv` (see that file for the actual addresses/roles), one step short of
what `original-game-spec` normally expects as input. Treat this as a punch list of "go look at
this before deciding if `open-populous` needs anything," not as finished findings.

## Provenance caveat (applies to everything below)

Traced this session (2026-10-30) against a copy of `D3DPopTB.exe` that does **not** match the
sha256 pinned in `Makefile` - spot-checked byte-identical to `backup/backup.xml` at three
independent landmarks (`process_tribe_cmd`/0x43e8e0, the `process_cmd` switch at 0x4aab80, and
`switchD_00d1138f`), but not exhaustively verified. Low risk, but worth re-confirming against the
exact pinned build before anything here is treated as final.

## 1. `tribe_cmd` opcodes queued from `process_cmd` (0x14, 0x15, 0x17, 0x1f, 0x20, 0x28, 0x29, 0x5f) - RESOLVED, mostly not actionable

Update (2026-10-30, later same day): all 7 original handlers (plus a newly-found companion,
0x20) have now been traced in `docs/commands.tsv`. Net result - **none of this looks like a
missing player-facing feature**:

- **0x14**: calls a 1-byte `ret` stub - a genuine no-op, nothing to port.
- **0x28 / 0x29**: their predicate helpers (`0x442f40`/`0x443260`) both build a message using
  template `0x5999ec` via `0x4fffe0` - the EXACT template/helper `ui_cmd 0x51`'s row already ties
  to the hidden "BYRNE" cheat text-entry overlay. Very likely more of that same cheat subsystem,
  not a "game speed" setting as `tribe_cmd 0x29`'s own 0-4 threshold byte might otherwise suggest.
  Matches this file's section 5 prediction.
- **0x1f / 0x20**: a clean start/stop pair showing a banner via the shared `0x479f00` dispatcher -
  plausible real feature, but no banner text/trigger was identified, so still unclear if it's
  worth anything to `open-populous`.
- **0x15**: a stepper (range 0-4 or 0-32 depending on a flag) that announces the new selection by
  name via a message table - plausible real feature (e.g. cycling some list), but what's actually
  being selected wasn't identified.
- **0x17**: the one genuinely open lead - its callee `0x443520` indexes a 0x34-byte-stride table
  at `0x5a8ab8` (the list `ui_cmd 0x49-0x4e`'s "select next/previous" cluster cycles through) with
  a type-tag sub-dispatch not yet read. Worth a dedicated pop3-rev session before concluding
  anything.
- **0x5f**: a clean, fully round-tripped per-tribe flag toggle (`tribe_struct+0x93d` bit 0x80,
  sibling to tribe_cmd 0x41's "all mana" bit 0x8) - functionally simple, but what the flag
  controls isn't confirmed, so still nothing concrete to port.

**Conclusion for `open-populous`**: nothing here currently warrants a TODO.md entry - the two
items with the clearest cheat/debug signature (0x28/0x29) are probably skippable the same way
section 3's UI-state bitmask is, and the remaining ones (0x15/0x17/0x1f/0x20/0x5f) need their
*purpose* identified (what list, what mode, what flag) before they're spec-ready, not just their
mechanics. Leaving this section in as a pointer rather than removing it, in case a future session
resolves `0x443520`'s table and it turns out to be something `open-populous` actually needs.

## 2. Notification "clear/dismiss all" (ui_cmd 0xb7 / 0xb8)

`ui_cmd 0xb7` sets 6 bytes at `0x89d168-0x89d16d` to 0xff; `ui_cmd 0xb8` zeroes them. This is the
same table functions.tsv's `0x40bd20` row (watchtower rally) ties to pop3-rev-analysis.md's
existing "Notifications" feature. If confirmed as a real player action, this reads like
"dismiss all notifications" / "clear all notifications" - worth checking whether
`open-populous`'s notification system already exposes an equivalent action, and adding a
TODO.md entry there if not. Not independently confirmed as a live keybind this session.

## 3. UI-state bitmask `0x98e908`/`0x98e909` - probably skip, but confirm first

A cluster of `ui_cmd` ids (0x47/0x48, 0x4f/0x50, 0xa0/0xa1/0xa2/0xa3, 0xa4-0xab, 0xbb/0xbc,
0xbd/0xbe) just set/clear individual bits of one 16-bit word. Reads like a HUD/debug-overlay
visibility bitmask (one bit per panel), i.e. likely original-developer debug tooling, not a
player-facing feature a clean reimplementation needs. Recommend a quick live-memory check (toggle
a bit, see what appears/disappears on screen) before deciding - if it's genuinely dev-only, the
right `open-populous` action is probably "note as intentionally not implemented," not a TODO to
build it.

## 4. Camera/zoom stepper commands (ui_cmd 0x32-0x3f) - cross-check against `camera.md`

Two min/max byte pairs (`0x89ce3f`/`0x89ce40`, enforcing a minimum-3 gap) and two signed
offset axes (`0x89ce45`, `0x89ce49`, step 200, range ±28160), plus two unclamped byte counters
(`0x89ce41`, `0x89ce42`). Possibly a free/debug camera control scheme. `docs/camera.md` already
has a working log of camera/flyby tribe_struct fields - a pop3-rev session should check whether
these globals overlap with anything already found there before this goes anywhere near
`open-populous`.

## 5. More debug/cheat-cluster candidates (ui_cmd 0x3e/0x3f, 0x40-0x42) - partly confirmed

Resolved by section 1's update: `ui_cmd 0x40-0x42` (-> tribe_cmd 0x28/0x29) are now fairly
strongly tied to the BYRNE cheat text-entry subsystem (shared message template with `ui_cmd
0x51`), so likely safe to skip for `open-populous`. `ui_cmd 0x3e/0x3f` (-> tribe_cmd 0x15, the
stepper) did NOT show the same cheat-template signature - still an open question whether it's a
real feature, see section 1.

## 6. AI-script interpreter (`interpret_script`) vs. `ai-scripts.md` (2026-10-30)

Follow-up to the user's "check how the AI works" question: `open-populous3`'s `docs/specs/ai-scripts.md`
(community-sourced - PopScript Wiki, the ALACN editor, `popscript-upgrader`'s Lua converter - cross-checked
against the 58 shipped `cpscrNNN.dat` files) already documents essentially the whole PopScript language and
its ~200 opcodes. This session read ~30 of `interpret_script`'s (`0x48CC60`, `docs/functions.tsv`) opcode case
handlers directly in the disassembly to check that community-sourced doc against the real exe. Read-only
reference clone used for comparison only, at `/home/user/ragusa87/open-populous3` (not written to). Full detail
is in each opcode's own `functions.tsv` row (`0x48cc94` onward); summary for whoever ports this:

- **Confirms `ai-scripts.md`'s id/parameter tables exactly** for every opcode read: all ~24 `STATE_*` toggles,
  `ATTACK`'s 13-parameter signature, `SPELL_ATTACK`, the whole marker/base-marker/drum-tower cluster,
  `SET_SPELL_ENTRY`, `SET_MARKER_ENTRY`/`MARKER_ENTRIES`, `DISABLE/ENABLE_USER_INPUTS`, `NAV_CHECK`,
  `SET_BUCKET_COUNT_FOR_SPELL`. No corrections to the opcode table itself.
- **New: the `STATE_*` storage mechanism**, undocumented before (community sources never had the exe). Every
  plain on/off state (all but `SPELL_DEFENCE`, which takes extra `x z` operands) sets or clears one bit of a
  single 32-bit flags word at `tribe_struct+0x59a` - bit index = the internal state number the wiki/Lua
  `CP_AT_TYPE_*` numbering already uses (0 = `CONSTRUCT_BUILDING` ... 23 = `BUILD_OUTER_DEFENCES`). If
  `open-populous`'s own tribe/AI data doesn't yet have an equivalent per-tribe 24-bit (round up to 32) states
  field, this is the concrete layout to add one from.
- **New: `SET_BUCKET_COUNT_FOR_SPELL` resolved.** This is the single highest-use DO command in the entire
  corpus (1502 uses across 47 files - more than double any other command) but `ai-scripts.md` marks it totally
  unknown. It's simple: `target_struct[spell_id*4 + 0x53f] = n` (a byte, 4-byte stride, per spell model).
  Almost certainly what `SET_BUCKET_USAGE` (1172, not traced) gates - the per-spell share of the AI's mana
  "bucket" spend. Worth a TODO.md entry once `open-populous`'s own mana-economy AI exists: every real script
  calls this once per spell at setup, so it's load-bearing for matching the original's spell-casting mix, not a
  minor/debug knob.
- **New: several "0 uses in the shipped files" opcodes are real, not dead.** `ai-scripts.md` lists
  `RESET_BASE_MARKER`, `SEND_GHOST_PEOPLE`, `GUARD_AT_MARKER`, `RESET_CONVERT_MARKER` and `SET_CONVERT_MARKER`
  as 0/0 uses; all five have genuine non-stub handlers in the exe (confirmed NOT the shared "unknown opcode"
  bailout at `0x48e763`), unlike the opcodes that really are absent (`STATE_SHAMAN_DEFEND`, the `SPARE*`/
  `ATTACK_BLUE/RED/YELLOW/GREEN` block, which DO hit that bailout). These are genuine unused features worth
  modelling if/when `open-populous` builds out the rest of PopScript, not opcodes to skip as dead.
- **New: `ai-scripts.md`'s open item, "what `SET_ATTACK_VARIABLE` receives," has a lead but isn't resolved.**
  `ATTACK` itself (`0x48cd07` -> `0x48fc50`) was traced in full down to the call into `0x4e5fd0`; the other 12
  ATTACK parameters' exact mapping onto the task record wasn't decoded, so this is still open.
- **Biggest finding: PopScript's `ATTACK` and the computer player's own autonomous AI are the SAME mechanism,
  not two parallel systems.** `0x4e5fd0` (ATTACK's real worker, reached via `0x48fc50`) turned out to already
  be catalogued, from an earlier unrelated session, as one of ~21 small "AI goal evaluator" functions
  (`0x462790`'s row) that the native AI's own "decide on a new goal" tick (`0x4625E0`, fires ~1/64 turns per
  tribe) calls to conditionally enqueue a task into one of the tribe's 10 round-robin AI task slots. Tracing
  `0x4e5fd0` this session found it ends by enqueueing task type `0x14` (20) - which is EXACTLY task id 20 of
  `maybe_ai_func_1`'s (`0x4623E0`) per-turn task dispatcher, whose handler `0x4CB400` was independently traced
  in yet another earlier session as "a per-tribe-person sweep issuing ordinary attack orders." So: a script's
  `DO ATTACK` doesn't bypass the native AI or duplicate its logic - it just manually fires one of the same
  internal "should I attack" evaluator functions the AI's own goal-picking tick calls on its own, which
  enqueues into the exact same task queue, executed by the exact same per-person sweep that would also run for
  an autonomously-decided attack. **For `open-populous`**: if/when the native computer-player AI and PopScript
  are both implemented, this says they should share one task-queue data structure and one "give this tribe an
  attack order" function, with PopScript's `ATTACK` command and the AI's autonomous attack-goal check being two
  different CALLERS of that one function - not two separate attack-order code paths that both need maintaining.
  This matches `ai-scripts.md`'s own "What this means here" section, which already recommends keeping AI
  behaviours as plain simulation data a script sets - this extends that to "and the native AI reads/writes the
  same data/queue a script would."

### 6a. Follow-up (2026-10-30, same day): EVERY's exact timing resolved; task-queue architecture mapped

Direct answer to the user's architecture question ("the script gives direction, the engine has its own
build/train/convert logic and decides combat") - **confirmed by the exe**: PopScript runs through two layers.
`interpret_script_upper` (`0x48c730`, new row) is the statement-level interpreter (`IF`/`EVERY`/`SET`/etc.);
it calls `interpret_script` (`0x48CC60`) only for `DO` commands, which in turn either write directly into the
tribe's own flags/attributes/tables (`STATE_*` bits, `SET_BUCKET_COUNT_FOR_SPELL`, `SET_SPELL_ENTRY`, marker
records - all queued from section 6 above) or - for `ATTACK` specifically - plug into the SAME native
per-tribe task-queue the autonomous AI tick (`process_tribe_2`/`0x461662` -> `maybe_ai_func_1`/`0x4623E0`,
10 round-robin task slots per tribe) uses for its own decisions. That queue, its ~24 task types, and the
engine's own economy logic (build/house/train/convert, the `STATE_*` flags presumably gate) are what actually
drives the AI turn to turn - the script mostly configures it rather than running it directly, exactly the split
the user described.

- **`EVERY n [m]`'s exact formula, settling an open item in `ai-scripts.md`/`open-populous` `TODO.md` ("the
  EVERY off-by-one and whether there is a per-tribe phase")**: confirmed as `(turn + tribe_num + m) % n == 0`
  (as a bitwise AND against the stored `n-1` mask, see `0x48c730`'s row for the exact mechanism), where
  `tribe_num` is a real per-tribe-struct byte (`tribe_struct+0xc22`, `backup.xml`'s own name) - **the original
  exe DOES add a per-tribe phase**, the same way `ai-scripts.md` only knew the Reincarnated Lua converter to
  do. Safe to port this exact formula when implementing `EVERY` timing.
- **Task-queue architecture, mapped but not fully decoded**: all 20 of the native AI's ~21 "goal evaluator"
  functions (each a potential entry of a 12-slot-per-tribe prioritized dispatch at `tribe+0x36e`, called from
  `0x4625E0`'s "decide a new goal" tick) were matched to the literal task-type id each one enqueues - table in
  `0x462790`'s (`set_sub_struct`) `functions.tsv` row. Only 2 of ~24 task ids have a traced HANDLER (what
  actually happens once dispatched): id 20 = the attack sweep (`0x4CB400`, shared with PopScript's own
  `ATTACK`), id 9 = a lightweight reschedule/no-op-ish task (`0x4C5CF0`). The other ~13 confirmed-real ids
  (0,1,4,6,7,8,11,14,24-28) are unidentified - this is where "convert wildmen first, then build houses, etc."
  and any population-triggered behaviour would live, but none of it is traced yet.
- **Checked specifically for the user's "tribe nearly wiped out -> send everyone to attack" claim - not
  confirmed, no counter-evidence either.** None of the 20 evaluators were found pushing task id 20 (the known
  attack task) except `ATTACK`'s own script-side evaluator (`0x4e5fd0`) - so if this behaviour exists, it's
  either one of the ~13 untraced task ids (most likely one of the higher, less-common ones, 24-28, found only
  this session and not yet in any doc), or it lives in code this session didn't reach at all (the per-evaluator
  CONDITIONS, which appear to live in the 12-entry table's own callers/setup rather than inside the evaluator
  functions themselves - only one evaluator, `0x4e6440`, was read in full, and it was unconditional). Also
  checked `GIVE_UP_AND_SULK` (1221, the one scripted "give up" command) as the closest documented analogue:
  **corrects `ai-scripts.md`'s "everyone guards the shaman" framing** - it actually sets a generic tribe
  "force success" flag (`tribe_struct+0x941` bit `0x40`) ALSO used elsewhere to force preacher-conversion rolls
  (`0x4D83B0`'s row) and other level-script-forced outcomes (`0x41CC20`) - broader than a self-contained
  retreat routine, and still framed as giving up/defensive, not an all-out attack. **Net: the user's general
  model (script sets goals, engine's own continuous tick runs the economy and decides moment-to-moment
  behaviour, including combat) is confirmed by this session's findings; the specific "desperate last stand"
  behaviour needs a dedicated future session tracing the untraced task ids (0x462568's dispatch table, one row
  per id) or `0x41ca10` (`GIVE_UP_AND_SULK`'s own callee) to pin down.**

### 6b. Follow-up (2026-10-30, same day): the AI's actual priority list found; last-resort mechanism traced

Found the structure answering "what order does the AI try things in." The per-tribe AI init function
(`0x461d70`, called from `clear_tribe` when a tribe is set computer-controlled - new row) copies a **fixed
240-byte TEMPLATE from a global at `0x59d878`** into every computer tribe's own 12-entry goal-category table
(`tribe+0x36e`, the table `0x4625E0`'s "decide a new goal" tick loops over). Dumped that template in full
(`0x59d878`'s own `functions.tsv` row) - **every computer tribe runs through the exact same 12 categories in
the exact same priority order**, trying each until one does something:

- **Position 0 (tried first, every tick): "construct essential buildings"** (`0x4e5580`, category id 1) -
  confirms `ai-scripts.md`'s `STATE_CONSTRUCT_BUILDING` really is the AI's top automatic priority, not just a
  switch with no special precedence. Gated by per-tribe-num/difficulty threshold bytes, it checks several
  building types (literal ids 4/13/15 plus a data-driven list) against how many it already has, and enqueues a
  now-confirmed **generic, parameterised "build a building of model N" task (task type 0)** for whichever is
  short. Nice `open-populous` implication: task type 0 isn't "build a hut" specifically, it's "build model N" -
  one task type, many building models, matching a config-driven building-priority list rather than hardcoded
  per-building logic.
- **Position 11 (tried LAST, only if all 10 others declined): the AI's one last-resort category** (`0x4e58b0`,
  category id 0xa) - gated by a single condition (`0x4f5f40`, own row): walk every person in the tribe
  (`tribe+0x881`'s list) and check whether ANY of them has bit `0x40000` set in their own `+0x10` flags field.
  If so, fires task type 5 - a task otherwise **unreachable from anywhere else in the entire AI** (checked
  across all 20 other goal-evaluator functions this session catalogued).
- **Task 5's handler** (`0x4c8070`, updated row - was a stub from an earlier session, fully traced now): sweeps
  every flagged person, clears the flag, and forces each one into **person state 14** ("idle/fidget" per
  `person_states.tsv`, though that row itself already flags ambiguity - `0x434610` separately ties state 0xE to
  "just finished entering a building"). Then does tribe-wide follow-up: clears marker targets (`-1,-1,-1`, the
  same convention `ATTACK`'s own unused markers use), something notification-shaped (`0x435730`, args resemble
  the `0x44d7f0` category-based notification system), and writes a likely cooldown (`tribe+0x5b1 = 20`).
- **Verdict on the user's "tribe nearly wiped out -> all units attack" hypothesis: settled, and it's not this.**
  Found what actually sets the `+0x10` bit `0x40000` flag `0x4f5f40` scans for: it's the exact same **"just
  converted" flag `0x4D83B0`'s own row already documents** on the preacher-conversion success path ("sets two
  'just converted' flags on the new unit, `+0x10` bit `0x40000`, `+0x14` bit `0x1000000`") - confirmed by
  matching disassembly byte for byte. So this whole last-resort category is the AI's **"integrate freshly
  converted/replaced followers" cleanup sweep** (reset them to idle, state 14, clear stale markers, notify,
  set a cooldown) - not a population-crisis attack trigger at all. It makes sense as the AI's lowest priority:
  processing new recruits is housekeeping that should never preempt building/attacking/defending. Also found a
  SECOND place that sets the same flag, a standalone "kill old unit, allocate replacement" helper (`0x4d7fd0`)
  called from two not-yet-identified sites (`process_flatten_land`/`0x50cabe` - surprising name for this, and
  `FUN_00512350`/`0x51256c`) - worth checking if either is a different mechanic that also creates "just
  converted" units and would likewise feed this cleanup category.
- **So the user's actual observed behaviour is still unexplained** - it isn't task 5, and none of this
  session's traced categories (position 0 "build", position 11 "integrate converts") are it either. Next place
  to look: the 9 remaining untraced priority-template positions (1-10, category ids 0,3,4,5,6,7,8,9,2,0xb -
  `0x59d878`'s row has all 11 remaining function addresses) or the `INT_ATTR_RETREAT_VALUE`/
  `INT_ATTR_BASE_UNDER_ATTACK_RETREAT` attributes (`ai-scripts.md`'s own attribute table, both still "?") -
  neither was reached this session.
- Smaller bonus find in `0x461d70`: pinned down where the raw `cpscrNNN.dat` bytecode actually lives once
  loaded - a flat 4×12552-byte buffer at `0x95f7b2` (one slot per tribe_num), pointed to by a 4-entry table at
  `0x9608b2`. Also found a tiny synthetic "empty script" (`{ } SCRIPT_END`, 6 bytes) written per tribe_num near
  `0x95d7b4` - likely what a computer tribe with no real script assigned runs, one level more primitive than
  the on-disk 34-word stub scripts `ai-scripts.md` already documents for multiplayer levels.
- Two more per-tribe arrays zeroed at init but not yet identified: `tribe+0x476` (10 entries × 8 bytes) and
  `tribe+0x4ce` (8 entries × 12 bytes) - good candidates for `SET_MARKER_ENTRY`'s and `SET_SPELL_ENTRY`'s own
  storage respectively (slot counts/record sizes line up plausibly), not confirmed.

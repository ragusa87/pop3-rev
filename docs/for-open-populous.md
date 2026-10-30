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

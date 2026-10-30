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

## 1. Five new `tribe_cmd` opcodes queued from `process_cmd` (0x14, 0x15, 0x17, 0x1f, 0x28, 0x29, 0x5f)

Found this session via `docs/commands.tsv`'s new `ui_cmd` rows (0x10, 0x14, 0x3e/0x3f, 0x40-0x42,
0x44, 0x49-0x4e, 0x97). Only the QUEUEING side is traced (which `ui_cmd` pushes which opcode with
which literal args into `set_tribe_command`) - nobody has read `process_tribe_cmd`'s own
`switchD_0043e922` handler for any of these 7 raw tribe_cmd ids yet, the way existing rows like
tribe_cmd 0x31/0x76/0x45 were traced end-to-end.

**Before writing anything to `open-populous`**: a pop3-rev session should trace these 7 handlers
in `process_tribe_cmd` first. Only then is it possible to say whether `open-populous` is missing
a feature (needs a TODO.md entry + spec section) or whether these are more of the same
debug/cheat-cluster machinery already noted as probably-out-of-scope (see tribe_cmd 0x31's own
row and section 5 below).

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

## 5. More debug/cheat-cluster candidates (ui_cmd 0x3e/0x3f, 0x40-0x42)

`ui_cmd 0x3e/0x3f` queue tribe_cmd 0x15 (a +1/-1 "cycle" stepper); `ui_cmd 0x40-0x42` queue
tribe_cmd 0x28/0x29, gated the same way as the existing BYRNE cheat cluster (tribe_cmd
0x31/0x76/0x45/0x41/0x44/0xc/0x1c - see those rows). Likely more of the same "probably not needed
for a clean reimplementation" cheat/debug family already flagged in `docs/commands.tsv`, but
should be traced (section 1) before being written off - if any of these turn out to be a real
exposed feature rather than a cheat, that changes the answer.

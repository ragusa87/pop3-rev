# Audio: sound effects, ambience and music

Working log for how `D3DPOPTB.EXE` plays audio: the sound-id → sample table, the play/stop API, the bank files,
the ambience bed, the battle loop, and the music (drones + drums, or CD audio). The per-id trigger catalog is
`docs/sound.tsv`; this file explains the machinery behind it. Bank file formats: `open-populous`
`docs/specs/sound.md` (the extractor is `open-populous` `tools/sprite_catalog.py`, `just sprites` →
`target/audio/<bank>/NNN_name.wav`, `NNN` = 0-based entry index).

## Banks (`Sound/`, loaded once by `init_hw_sound` 0x48B950)
| Handle global | File | When |
|---|---|---|
| `0x5AE2A4` | `soundd2.sdt` | "high quality sound" option on (`0x895DA8` bit `0x4000000`, read by `0x4998B0`) |
| `0x5AE2A4` | `soundd2low.sdt` | same option off - same ids, 11 kHz, different variants per index |
| `0x5AE2AC` | `popdrones22.sdt` | always tried; sets `0x895DB3` (drone music available) |
| `0x5AE2BC` | `popfightnew.sdt` | always tried; sets `0x895DB6` (fight bank available) |
| `0x5AE2BC` | `popfight.sf2` | fallback only if `popfightnew.sdt` failed (`0x895DB6` = 0, fight ids then use their `soundd2` fallback samples) |
| `0x5AE2B4` | `popdrum{N}22.sdt` | loaded each time music (re)starts, `N` = random 0-9 (digit patched into the name at offset 7) |

All sample indices the game passes to the mixer are **1-based** (entry `k` of a bank = sample index `k+1`;
0 = "no sound").

## Sound id table (`0x5ACF60`, 12 bytes per id, ids `0x00`-`0xE4`)
| Off | Size | Meaning |
|---|---|---|
| +0 | u16 | first sample in `soundd2` (1-based; 0 = no sound - the id is silent) |
| +2 | u16 | first sample in the fight bank (used only when +0xB != 0 and the fight bank loaded) |
| +4 | u8 | animation-sync frame: when not `0xFF`, a positional sound waits (pending) until its unit's frame byte `+0x39` equals this value, so the chop lands on the axe frame (`0x01` chop/eat/drink/build/wildman eat-drink, `0x03` stomp) |
| +5 | u8 | variant count in `soundd2`: one of `[first, first+count)` is picked at random per play |
| +6 | u8 | variant count in the fight bank |
| +7 | u8 | priority (0x20 faint ambient ... 0xB4 spells, 0xE6 volcano rise, 0xFF UI/voices) |
| +8 | u8 | pitch spread in percent: the channel stores 100 ± random(spread), but nothing ever reads it and no frequency change is ever sent to the mixer, so this is **dead data: every sample plays at its native rate** |
| +9 | u8 | runtime: number of channels currently playing this id (incremented on play) |
| +0xA | u8 | volume 0-127 |
| +0xB | u8 | non-zero = use the fight bank (`popfightnew.sdt`) instead of `soundd2` when it is loaded |

Ids with +0xB set: `0x0D`, `0x0E` (punches, `Punch*`), `0x27` (swords), `0x2B` (sword flashes `sw_flsh*`),
`0x2D`-`0x30` (attack yells `Attk01..03`, `Attk99`), `0x32` (hit grunts `v_hit*`). Their `soundd2` fallback
range is unrelated junk (`convert..sitespel`, `chop*`), so the fight bank is effectively required.
The full decoded id → sample-family list is the `name` column of `docs/sound.tsv`.

## API
- `0x48A050(unit, id, flags)` - play. Returns the channel (0 if suppressed). Behaviour:
  - Suppressed when: sound off (`0x895DAF`/`0x895DB0`/`0x895DB2` clear); the game is paused (`0x89C661` bit 2)
    unless flags has `0x800` (pause-menu clicks use `0x801`); an overlay/special view is up (`0x89C6C1`==2 or
    `0x89CE36` != 0) and the sound is positional (`unit` != 0) or is one of the random ambient one-shots
    `0x1C`/`0x50`/`0xC2`/`0xC6` - i.e. only UI sounds play over those screens.
  - Positional (flags bit 0 clear): needs the unit within 48 cells of the listener point, or it is not played
    (see "Mixer, distance and effects" for falloff and pan). Id `0x19` (shaman "yes") on the local tribe's own
    shaman is never culled: its distance is clamped to 3/4 of the cut-off.
  - Flags bit 0 set: 2D/UI sound, full volume, no distance test.
  - Flags `0x4`: an ambience-bed slot (pan/slot index picked from the id, volume = bed weight × table volume,
    re-evaluated by `0x4895C0`; that helper also mutes the hell variants outside the hell theme and vice versa).
  - Flags `0x2`: true loop - the same sample repeats (9999 times) until stopped (`warloop`, Shield hum, and the
    restart-style rumbles of erosion/lava/quake/volcano).
  - Flags `0x10`: remember the unit's `+0x33` (animation id); if it changes before the sound actually starts
    (still waiting for its sync frame), the sound is dropped.
  - Flags `0x40`: chained variety loop - each time the sample ends a NEW random variant of the id is queued
    (callback `0x48C440`), until `0x48A770` stops it; the stop lets the current variant finish rather than
    cutting it (fire, whirlwind, swarm, swamp, guard post, boat/balloon ride, burning building).
  - Flags `0x800`: still plays while paused.
  - Ids `0x74`-`0x86` (local shaman's spell shouts): not replayed while one is already playing on the same unit.
- `0x48A770(id, unit)` - **stop** the channel playing `id` (on `unit`, or any if 0). Returns 1 if one was found.
  (`sound.tsv` previously read the 0x408B80 call as a "positional play" - it is the burning-building crackle stop.)
- `0x48B450(x)` stop every channel; `0x48B480` / `0x48B4B0` pause / resume every channel; `0x48B4E0` global
  mixer state change.

## Mixer, distance and effects
Back end: QSound's `QMIXER.dll` (QSWaveMix* API) under a C++ wrapper (`0x89CE71`, vtable `0x593E38`; QMixer back
end vtable `0x593F38`, one thin method per import at `0x56F3xx`-`0x5700xx`), with Creative EAX 1.0 reverb on top.
Session: 15 mixer channels (`0x48B9D9`); a quality preset bit (`0x400` high / `0x200` low quality option).

**Voices (`0x48ABB0`).** At most 10 game sound channels (the rest of the mixer's channels are left to music).
- The same id cannot restart within 250 ms of its last start (timer `0xD0C784`): the new request is dropped.
- When 10 are playing, each live channel gets a score = priority (table +7) × 256, halved once per 16 steps of
  remoteness (positional only, see `closeness` below), × 1024, then halved once per live copy of the same id
  (twice per copy for looping/chained ids). The lowest-scoring channel is the victim. The new sound is scored
  the same way from its own distance. If it scores at least as high, the victim is cut (no fade) and the new
  sound takes its place; otherwise the new sound is dropped. Net: faraway, common or repeated sounds give way
  to near, rare, high-priority ones (spells 0xB4, volcano 0xE6, UI/voices 0xFF).

**Listener point.** The camera's look-at point (camera block `0x74A350` +0x24) moved 16 cells (0x1000) along the
camera's heading (`+0x32`) by `0x4E6A70` - i.e. roughly under the viewer, not at the screen centre. Distances use
the wrapped map (`0x450450`, squared 2D, height ignored).

**Distance and pan (`0x48B100`, recomputed every frame by `0x48A900` while the unit lives).**
- `d²` = squared distance unit→listener; cut-off `D² = 0x9000000` (D = 12288 units = 48 cells). Beyond it: the
  channel is silenced and, during the per-frame update, stopped without fade (a chained loop finishes its current variant).
- `closeness = 127 × (1 − d²/D²)` (quadratic falloff, 127 on top of the listener, 0 at 48 cells). The game also
  keeps `table volume × (1 − d²/D²)` per channel, but uses it only as a "still audible" gate and for voice
  stealing; it is not the volume it sends.
- `pan` = bearing of the unit seen from the listener, relative to the camera heading + 90°, folded into 0-127
  (64 = straight ahead or straight behind - front and back are not distinguished, both map to the same side).
- What is sent to QSound: full table volume × master SFX volume (`0x895DB4`)/127, and a **polar 3D source
  position**: azimuth = `-90°..+90°` from the pan (float table `0x5AE098`, linear, 64 → 0°), range =
  `(127 − closeness) × 16` (0 at the listener, 2032 at the cut-off), elevation 0. So the audible loudness falloff
  and the stereo/3D image are QSound's own rendering of that range/azimuth (QSound's default distance model, never
  configured by the game), on top of the game's hard 48-cell cut-off. Updated every frame as the unit or camera moves.
- 2D/UI sounds (flags bit 0): volume = channel volume × master/127, polar position azimuth 0, range 112 (fixed,
  just in front of the listener).
- Ambience-bed slots: as 2D, with the bed weight applied (`0x4895C0`).

**Effects actually used.**
- Reverb: EAX 1.0 (`DSPROPSETID_EAX_ReverbProperties` {4a4e6fc1-c341-11d1-b73a-444553540000}, set through
  `0x56EA60`/`0x56EAA0`, only if the sound card exposes EAX). In play: preset 19 (`0x5E4BFC` = 0x13; "Plain" in the
  EAX 1.0 preset list). In the special/overlay view: a custom reverb - environment 13 ("Stone Corridor"), volume
  1.0, decay 5.0 s, damping 2.0 (`0x4895A0`). Re-applied by the ambience pass whenever the view changes (`0x5AE2FC`).
- Fades (confirmed): done in software by the game's own sound library, not by QMixer. Play flag `0x1000` attaches
  a sample filter (`0x56D890` -> class `0x573C80`, vtable `0x594180`, process `0x573D00`) that multiplies each
  16-bit sample by a gain ramping linearly 0 -> 1 over N bytes of PCM (params +0x24); flag `0x2000` is the
  matching fade-out used on stop. N = 0x1400 for effects (5120 bytes = 0.116 s of 22 kHz mono): high-quality
  mode only, on stop (`0x48B010`) and on each new variant of a chained loop (`0x48C440`). N = 0x25800 for music
  (153600 bytes = 1.74 s of 22 kHz stereo), on music start (`0x48C230`, flags 0x21001) and stop (`0x48B8D0`).
- Orbiting sources: when a cinematic/UI swoosh is played through `0x48A810` (discovery cinematics, soul swirl,
  bookmark camera jump), there is a 50% chance it gets a mover (`0x47FED0`) that circles the listener at a small
  fixed radius, 60/2048 of a turn per frame, sent as a cartesian 3D position each frame.
- Random variant per play (all ids), and per repeat for chained loops.

**Imported but never used by the game:** SetFrequency (no pitch change at all, see table +8), SetSourceVelocity /
SetListenerVelocity / SetSpeedOfSound (no doppler), SetSourceCone, SetDistanceMapping, SetListenerPosition /
Orientation (listener stays at the origin; sources are placed relative to it), SetSpeakerPlacement, SetPanRate.
The wrapper can drive all of them, but no game code sets the corresponding parameter bits.

**Channel record** (game side, 0x2A bytes, list `0x89CE6D`): +0x8 mixer handle, +0xC unit id, +0xE sample,
+0x10 sound id, +0x12 pitch % (unused), +0x14 table volume, +0x15 pan, +0x16 audible volume, +0x17 priority,
+0x18 flags (caller flags | 0x108; 0x8 pending start, 0x20 cancelled, 0x80 finish-then-stop, 0x200 fading),
+0x1A bed slot / unit animation id, +0x1C/+0x20 callback and mover objects, +0x24 start time, +0x28 closeness.

## Selection and order voices
`0x489C40(selection, unit, single)` - called by `process_tribe_cmd` (0x4422AD, select command) and 0x444F31
(drag/box selection, `single` = 0):
- single unit: preacher `0x57` (`v_pre_bow`), spy `0x56` (`v_spy_bow`), shaman `0x18` (`Sv_sel`),
  anyone else `0x58` (`v_bow001-007`).
- group: counts per type in the selection, then layers up to four voices at once -
  spies 1/2/3/4+ → `0x56`/`0x46`/`0x47`/`0x48`; preachers 1/2/3/4+ → `0x57`/`0x49`/`0x4A`/`0x4B`;
  shaman present → `0x18`; everyone else 1/2/3/4+ → `0x58`/`0x43` (`v_bow2`)/`0x44` (`v_bow3`)/`0x45` (`v_bow3`).
  The 2/3/4+ ids of one type share the same samples (the "two voices / crowd" recordings).
Order acknowledgements (`v_ok*` ids `0x37`-`0x42`, `Sv_yes` `0x19`) are played by the command code - see
`sound.tsv`.

## Shaman spell shouts
`0x4C1B80` (spell object launch): the caster shaman shouts `0x74 + spell type` when the spell belongs to the
local tribe (`Sv_*` recordings), `0x8A + spell type` for any other tribe (`En_Sv_*`, the enemy-shaman voice).
Played on the shaman if alive, else (tribe flag `+0x93F` bit 8) as a 2D sound.
Spell type → shout: 1 burn & 2 blast `Sv_blast`, 3 lightning `Sv_bolt`, 4 whirlwind `Sv_wind`, 5 swarm
`Sv_insect`, 6 invisibility `Sv_invis`, 7 hypnotism `Sv_hypno`, 8 firestorm `Sv_fstm`, 9 ghost army `Sv_ghost`,
10 erosion `Sv_erode`, 11 swamp `Sv_swamp`, 12 land bridge `Sv_bridge`, 13 angel `Sv_angel`, 14 earthquake
`Sv_quake`, 15 flatten `Sv_flat`, 16 volcano `Sv_volc`, 17 convert `Sv_dance`, 18 armageddon `Sv_blast`.
Types 19-21 would index `0x87` (silent) / `0x88` / `0x89` (local) and `0x9D` (silent) / `0x9E` / `0x9F` (enemy),
which belong to other uses - so only reachable if those spells go through this launch path.

## Ambience bed (`0x489770`, every frame from 0x411212 / 0x4A4C9F)
Two layers:
1. **Terrain-weighted bed** (only with high-quality sound on). `0x489A30` fills five slots with a
   theme-dependent id and a weight computed from what the landscape renderer just drew near the camera
   (`0x467342`-`0x46738B` copies the draw counters into `0x895DC1`-`0x895DCB`):
   | Slot | Normal theme | Theme 16 | Theme 30 (hell) | Weight |
   |---|---|---|---|---|
   | 0 | `0x1D` `amb_m1*` | `0x1D` | `0xC7` `amb_hellm1*` | low-land cells ×256 / near cells |
   | 1 | `0x1E` `amb2*` | `0x1E` | `0xC8` `ambhell2*` | 2 × min(low-land, water) - shoreline in view |
   | 2 | `0x1F` `amb_w1*` | `0x1F` | `0xC9` `amb_hellw1*` | high-land (height > 0x200) cells ×256 / near |
   | 3 | `0x21` `spacey*` | `0x21` | `0x21` | 0, or 255 in the overlay/special view (`0x89C6C1`==2 etc.) |
   | 4 | `0x20` `amb_sea*` | `0xD5` `amb_w2*` | `0xCA` `amb_hellsea*` | water cells ×256 / near cells |
   Theme = `0x895DCD`, set from the level when it loads (0x42A473). The slots are sorted by weight and the
   top three with a non-zero weight are (re)started as 2D bed sounds (flags 5) whenever not already playing,
   so the bed is a continuous cross-mix that follows the camera.
   Same pass also switches the mixer's environment preset (`0x5AE2FC` = 0x13 normally, 0xFF in the special view).
2. **Random one-shots / loops** (not in the overlay/special view):
   - seagulls `0x50` (`amb_gull*`): 1/256 per frame when every near cell drawn is water, not in theme 30.
   - "wildlife" one-shot 1/128 per frame when trees are in view (`0x895DC9` = near class-5 scenery types
     1-6 drawn): theme 22 → `0xC2` (`amb40xx`), theme 30 → `0xC6` (`amb50xx`), else `0x1C` (`amb10xx`).
   - Magical Shield hum `0xC3` (`Shield`, a looping sample): started (flags 3) while any unit with
     `+0x15` bit `0x80` is drawn near the camera (`0x895DCB` > 0, most likely shielded units), stopped
     when none is.
   - in the special view instead: `0x54` (`amb_spc*`, space ambience) 1/128 per frame.

## Battle loop (`0x489E50`, from `main_loop_inner` every turn)
`warloop` (`0x6C`, looping) is a crowd-of-battle bed. Per turn: reset; for every live melee fight record
(list `0x890358`) after the 6th, add a contribution growing as the fight gets closer to the local camera
target; then start `0x6C` (2D) if the total > 0 with volume = min(total, 127) × master volume, or stop it if 0.
So it is silent until at least 7 melee fights are running in the world at once.

## Music (`0x48B500` start, `0x48B8D0` stop, `0x48B850`/`0x48B890` pause/resume)
Started from the frontend (`draw_fe` 0x457AA4, game-mode byte `0x88F000` == 7), at level start / after a
video, and resumed from menus. Two modes, `0x895DB1`:
- **1 = streamed SDT music.** On each start: pick drone track `0x895DC0` = random 2-5 (`idea13`, `idea16`,
  `idea17`, `idea19`), or 1 (`idea11`) when `0x88F000` == 7 (frontend); load a random drum bank
  `popdrum{0-9}22.sdt`. The music object (`0x895DBB`, segment-finished callback `0x48C420` → `0x48C230`)
  first plays the drone, looped (count 9999), at music volume `0x895DB5`; every following segment is a
  drum loop picked from the **music intensity** `0x89D167`:
  - `0x89D167` is cleared at the top of every turn (`main_loop_inner` 0x4EC709), set to 1 by
    `attack_order_handler` (0x51A30B) when a unit of the local tribe runs an attack order, and to 2 by
    `pre_fight_turn` (0x5186BA, local tribe on either side of a challenge) or `fight_turn` (0x51917C, a
    local-tribe fighter in a melee). Copied into the music object each turn (0x4ECA35).
  - intensity 0 → drum sample 1 (entry 0, the bank's "a" loop); coming down from a fight first plays
    sample 2 once, then back to 1.
  - intensity 1 → sample 2 (entry 1).
  - intensity 2 → sample 3 (entry 2), and every 4th consecutive fight segment sample 4 (entry 3) if the
    bank has 4 entries (`PopDrum222` has 3, so it never gets this break).
  Net effect: ambient drone + calm drums, drums switch to the heavier loops while the player's own units
  attack or fight, and ease back afterwards.
- **2 = CD audio** (`0x89CE75` CD player object): plays CD track `0x895DBF` (option-selected, clamped to the
  disc's track count) via MCI; no drums, no intensity.
Pausing (`0x48B850`, from the in-game menus at 0x418973 / 0x4A45F7) and resuming (`0x48B890`) act on the
current music segment.

## Orphans (in the exe, never played)
Per id (`sound.tsv` rows with status `orphan`):
- Ids with samples but no reachable call: `0x0C` (chop), `0x17` (quiet `oh001`), `0x38`-`0x3A` (`v_ok2`/`v_ok3`,
  "two/three voices ok" - the order-acknowledgement jump table at 0x436434 only ever gets index 0 or 1),
  `0x63` (`Snapshot`), `0x66` (`selectfe`), `0xA5`-`0xA7`, `0xB1` (`fire`), `0xB7`-`0xBB` (`sitespel`),
  and the spell-type-0 shout slots `0x74`/`0x8A` (their `Sv_dance` samples are still used by convert, `0x85`/`0x9B`).
- Silent ids (no sample): `0x00`, `0x07`, `0x08`, `0x59`-`0x5F`, `0x61`, `0x62`, `0x64`, `0x65`, `0x67`-`0x69`,
  `0x87`, `0x9D`, `0xA0`, `0xD3`, `0xD6`, `0xDF`. `0x62` (pointer-mode reset) and `0x64` (minimap click) are
  still called: those calls are silent.
Per sample (`Soundd2.sdt` entries, 0-based):
- never referenced by the id table at all: 277-278 `Wdrop01/02`, 305-308 `En_Sv_grunt01-04`.
- referenced only by orphan ids: 2 `fire`, 9 `Snapshot`, 149 `selectfe`, 183-186 `v_ok2_*`/`v_ok3_*`.
- the `soundd2` fallback ranges of the fight-bank ids (`convert..sitespel`, `chop*`, `eat*`) only play when
  `popfightnew.sdt` is missing - effectively junk.
- the spell-record byte at `0x5A80D0`+0x30 (one sound id per spell) is never read: each effect hardcodes its own id.

## Sample selection details worth knowing (for `open-populous` `target/audio.html` readers)
- A sound **id is not a sample index**: always go through the 0x5ACF60 table (`sound.tsv` `name` gives the
  0-based `Soundd2` entry range, e.g. `v_land01..v_land07 [122-128]`).
- The low bank reuses the same table indices but its entries at those indices are other variants of the family,
  and 39 of them are empty `0x92` entries: in low-quality mode those variants play nothing.
- Drum bank entry 0 (flag `0x83`, the extractor's "placeholder") IS played: it is drum sample 1, the calm loop.
  Its data range starts 40 bytes early (on entry 1's header), so it is entry 1's loop with 40 bytes of header
  as a click at the start.
- Music index 1 (`idea11`) is the frontend track; 2-5 are picked at random per level.

## FMV audio
The movies (`FMV\p3intro1-3.tgq`, `p3introj.tgq`, `outro.tgq`, `pop3mask.tgq`) are EA `SCHl` streams with
EA-XA ADPCM audio, decoded by the exe itself (`0x57A2D0` dispatching to `0x57D870` mono / `0x57D9F0` stereo,
from the stream reader `0x579D40`). This codec is NOT the `soundd2low` one (the bank loader never reaches it).

## External cross-check: veritr1x/populous-recomp
A native macOS recompilation of this same exe (github.com/veritr1x/populous-recomp, audio layer in its
`recomp-kit` submodule, `dx/qmixer.cpp`). Read for facts only, nothing copied. Useful:
- QMixer volume is a linear amplitude 0..32767 (they read QMIXER.dll's own handler: gain = value/32767), and
  they report the game typically passes ~14190 (gain 0.43, about -7 dB). Not re-checked here.
- Streamed waves (music) are fed by a game callback in chunks of 0x7800 or 0x3C00 bytes (`0x56F8DA`, callback
  `0x576660`); a zero return marks the stream finished. Consistent with the music object's segment chaining.
- The game hands QMixer plain PCM with a WAVEFORMATEX (no RIFF, no compressed format tag) - so the low-bank
  codec, if used, is decoded by the game's own library before QMixer sees it.
- Their QMixer replacement ignores 3D position, distance mapping and cones (plays everything centred), so it is
  not a reference for the positional behaviour described above.
- They confirmed the EA-XA decoders above against the intro movies.

## `soundd2low.sdt` codec: EA MicroTalk (UTK)
Identified statically and **confirmed by decoding** 2026-11-17: all 414 non-empty `0x10` entries decode with a
stock MicroTalk decoder once the leading bit below is handled; lengths match the `Soundd2` entries (median ratio
1.01, the excess is the last frame's padding) and, where both banks hold the same recording, the waveform
correlates 0.95-0.99 with the `Soundd2` one (downsampled to 11 kHz).
- Bank source factory `0x570590` (entry flags byte +0x1B): `0x80` placeholder class, `0x20` MPEG class, **`0x10`
  -> class `0x577960`** (in-memory, vtable `0x5949A0`) or `0x577C30` (streamed, reads 0x2000-byte chunks via
  `0x578C00`), else plain PCM. Plain PCM gets a PCM WAVEFORMATEX from the header (`0x571150`: channels =
  1 + flag bit 0, rate = header +0x18, bits = +0x1A).
- Decoder: header parse `0x578B10`, excitation decode `0x578900`, per-channel frame decode `0x578D00` (+ synthesis
  `0x5790A0`), frame driver `0x5798E0`, output `0x577B20` (432 float samples per frame per channel, clamped to
  int16; channel state stride 0xD34, second channel at +0xD48; state block 0x1A7C bytes).
- Why MicroTalk: LSB-first bit reader seeded from the first byte; 432-sample frames of four 108-sample subframes;
  12 reflection coefficients; a 64-entry fixed-gain table built geometrically; header fields read as 1 bit, then
  `32 - 4 bits`, `8 * (1 + 4 bits)`, `1.04 + 0.001 * 6 bits` (float constants at `0x594D20` = 8.0, 0.001, 1.04) -
  exactly the public description of EA MicroTalk ("UTalk"/UTK), a multi-pulse LPC speech codec at ~32 kbit/s
  ("MicroTalk 10:1"), first shipped by EA in Beasts & Bumpkins (1997). Public-domain reference decoders:
  github.com/daddesio/utkencode (`utk.h`), wiki.niotso.org/UTK; also in vgmstream (EA MT).
- Populous variant: every low-bank entry (flag `0x04` clear) starts with ONE extra bit, read LSB-first before the
  standard MicroTalk header: 0 = mono (data starts `e2 71`), 1 = a second channel follows (`e3 71`, the 21 stereo
  ambience entries `amb2*`, `amb_spc*`, `ambhell2*`, `discoend`, `discosky`). Stereo = both channels share the one
  header and one bit stream, alternating per frame: left frame, then right frame (`0x5798E0`), each with its own
  filter/history state. Standard MicroTalk is mono-only; this is the Populous extension.
- Oddity: the six `ambhell2*` entries decode ~1.41x longer than their `Soundd2` counterparts at their header
  rate (and don't correlate with them) - either a different recording or a header rate that isn't the encoded
  one; not chased.
- Rate: the decoder is rate-agnostic; the game plays the result at the entry's header rate (11025 Hz for most
  low-bank entries).
- Credits: the codec description used to recognise it (frame/subframe sizes, header fields and their constants,
  bit order, multi-pulse excitation, "first used in Beasts & Bumpkins") comes from daddesio's MicroTalk work,
  github.com/daddesio/utkencode (README and `utk.h`, released to the public domain via the UNLICENSE), and the
  Niotso wiki UTK page it links (wiki.niotso.org/UTK). Only facts were taken from it; nothing was copied into this
  repo. The exe-side addresses and the Populous stereo extension are this repo's own findings.
- Decoded copies for listening: `open-populous/target/audio/soundd2low_decoded/NNN_name.wav` (never committed),
  made with a scratch harness around daddesio's `utk.h` (drop the first bit; for stereo, two decoder states
  taking turns on the shared bit reader).

## Other public sources (checked 2026-11-17)
- No public decompilation or source of Populous: The Beginning. The OpenPop notes (github.com/OpenPop/notes) list a
  private repo built on "the official source code" (Brandantl/Populous-The-Beginning, not accessible) and
  OpenPopulous (an unofficial clone, not the original code).
- Dungeon Keeper 2 uses the same SDT container and 40-byte header (ufdada/dk2-tools `Formats/Sound/sdt_struct.bt`):
  types 2/3 PCM, 0x24/0x25 MP2 mono/stereo, flag 0x20 = MPEG, 0x04 = decoded-length field valid. It has no `0x10`
  compressed type, so the `soundd2low` codec is Populous-specific as far as public info goes.
- popre.net forum: music is MP2 converted from 44 kHz CD masters (by the game's composer), which fits the
  CD-audio music mode (`0x895DB1` == 2) playing those masters as CD tracks.
- No public QMixer SDK docs found; ScummVM's Titanic engine reimplements part of the QMixer API (qmixer.h).

## Open leads
- Exact channel semantics of the music object (whether the drone and the drum loop run on two channels or one
  queue) depend on the QMixer wrapper; the drum choice logic itself is traced.
- `0x895DCB` (Shield hum gate) counts drawn units with `+0x15` bit `0x80` - "shielded" is inferred, not checked live.
- Nothing has been checked by ear yet: every row is static (`traced`/`named`), none `verified`.

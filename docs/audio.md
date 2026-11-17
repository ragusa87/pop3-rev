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
| +4 | u8 | `0x01` on work/eat/drink/build ids, `0x03` on stomp, else `0xFF` - unread so far |
| +5 | u8 | variant count in `soundd2`: one of `[first, first+count)` is picked at random per play |
| +6 | u8 | variant count in the fight bank |
| +7 | u8 | priority (0x20 faint ambient ... 0xB4 spells, 0xE6 volcano rise, 0xFF UI/voices) |
| +8 | u8 | pitch spread in percent: pitch = 100 ± random(spread) (0 = fixed pitch) |
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
  - Positional (flags bit 0 clear): volume scaled by the distance from the unit to the local player's
    camera target (tribe struct +0x24); farther than the cut-off → not played at all. Id `0x19`
    (shaman "yes") is special-cased to attenuate only when the unit is the local tribe's own shaman.
  - Flags bit 0 set: 2D/UI sound, full volume, no distance test.
  - Flags `0x4`: an ambience-bed slot (pan/slot index picked from the id, volume = bed weight × table volume,
    re-evaluated by `0x4895C0`; that helper also mutes the hell variants outside the hell theme and vice versa).
  - Flags `0x10`: channel keeps following the unit (stores its `+0x33`).
  - Flags `0x40`: kept on the channel; every id played with it is a continuous sound that has an explicit
    `0x48A770` stop elsewhere (fire, whirlwind, swarm, swamp, guard tower, boat/balloon ride) - looping.
  - Ids `0x74`-`0x86` (local shaman's spell shouts): not replayed while one is already playing on the same unit.
- `0x48A770(id, unit)` - **stop** the channel playing `id` (on `unit`, or any if 0). Returns 1 if one was found.
  (`sound.tsv` previously read the 0x408B80 call as a "positional play" - it is the burning-building crackle stop.)
- `0x48B450(x)` stop every channel; `0x48B480` / `0x48B4B0` pause / resume every channel; `0x48B4E0` global
  mixer state change.

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

## Open leads
- `soundd2low.sdt` codec (flag `0x10`, data starting `e2 71`/`e3 71`): about 9x smaller than 11 kHz 16-bit PCM
  (~1.8 bits/sample). Not decoded in the exe's own code paths read so far: banks go through the C++ sound
  wrapper (`0x56xxxx`-`0x57xxxx`, vtable calls into `QMIXER.dll` QSWaveMix*), so the decoder is either in
  that wrapper or in QMixer itself. Next step: break on the wrapper's bank open (`0x56DDC0` -> `0x575430`) with
  low-quality sound on and see who touches an `e2 71` buffer.
- Exact channel semantics of the music object (whether the drone and the drum loop run on two channels or one
  queue) depend on the QMixer wrapper; the drum choice logic itself is traced.
- Mixer flag bits `0x2` (restart-style ambient: erosion, lava, quake, volcano rumbles) and table byte +4 unread.
- `0x895DCB` (Shield hum gate) counts drawn units with `+0x15` bit `0x80` - "shielded" is inferred, not checked live.
- Nothing has been checked by ear yet: every row is static (`traced`/`named`), none `verified`.

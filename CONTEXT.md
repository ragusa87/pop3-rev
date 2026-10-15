# CONTEXT: Populous: The Beginning — big-picture overview for exe inspection

High-level summary of what reverse-engineering has established so far about the original
game's dynamics, intended as orientation before diving into `D3DPOPTB.EXE` disassembly or
memory, and as a reference for any project documenting or reimplementing the game.

## 1. Units

Seven simulated person kinds: **Shaman, Brave, Warrior, Preacher, Spy, Firewarrior**, plus
neutral **Wildmen** (unconvertible until touched by a shaman/Convert) and **Angel of Death**
(person type 8, spawned only by its spell — a meteor followed by a creature that hunts the
nearest enemy anywhere on the map, pulling victims from buildings and killing up to 40
within ~208s — never placed directly in levels). The Angel is fully modeled/functional in
the original exe. Model IDs in level files: 1 wildman, 2 brave, 3 warrior, 4 preacher, 5 spy,
6 firewarrior, 7 shaman, 8 angel.

- Persons are "thing" records (kind = person) with a model (= unit kind) and an owning tribe
  (255 = none).
- Per-kind stats (health, speed, heal rate, attack strength) come from tuning tables in
  `constant.dat` — one row per kind. Shaman has by far the highest HP; spy/firewarrior are
  fast but fragile.
- Units run a state machine ("Action"): Idle, Walking, Stranded, Worshipping, Casting,
  Landing, work states for braves (Chopping, Flattening, Building, Hammering, Holding),
  Drowning, combat states (Attacking, Hacking, Throwing), fight sub-states via shared
  "coordinators" (Challenge, Melee, Sermon), Tumbling, and Dying/Dead/Spirit.
- Only the shaman reincarnates (at her tribe's site); any other unit's spirit rises and the
  unit is removed permanently.
- Orders can be chained/queued per unit.

## 2. Sprites, meshes, and poses

Units are **2D sprite-based**, not 3D meshes: each animation is a sequence of frames built
from chained 2D sprite elements (from the `HSPR0-0.DAT` bank) positioned around the unit's
feet, with layering for tribe-color recoloring and gear/outfit overlays on top of a shared
"tribesman body." There are 99 named animations (`VSTART`/`VFRA`/`VELE` tables), each with 8
facing directions (5 unique + 3 mirrored).

Buildings and scenery, by contrast, **are real 3D meshes** (point/face banks in
`objs`/`pnts`/`facs` files) — one-sided faces, textured from a per-level theme atlas, with
special alpha-blended "flame board" faces for fires/torches.

Discovered pose/animation families: walk, idle/breathing, firewarrior fire-throw, kneeling
prayer, brave work (carrying/chopping/holding wood, ground-flattening jump), fight moves
(punch, knockback, kick, reeling/stagger), spy arson disguise, being-converted sit-down,
tumbling (air/ground), dying fall, lying dead, drowning/spirit-rising, idle fidgets
(scratching, push-ups, juggling), vehicle pedaling, panic-run (bees), preacher sermon
gestures, and lightning-carbonized. The shaman has her own separate, per-tribe-colored
animation set (not layered like followers) covering the same categories.

## 3. Spells

18 player-selectable spells plus a few hidden/model-only ones (Burn, Teleport are
sandbox-only). Full model list: burn, blast, lightning, tornado/whirlwind, swarm,
invisibility, hypnotism, firestorm, ghost army, erode, swamp, land bridge, angel of death,
earthquake, flatten, volcano, convert, armageddon, magical shield, bloodlust, teleport.

Rough mechanical grouping:

- **Terrain-shaping**: Land Bridge (raises a sea path over time), Flatten (levels a disc),
  Erode, Raise, Volcano (multi-phase: rumble → rising/destructive crater → lava aftermath),
  Earthquake (sinks ground + lava fissure).
- **Direct damage/area**: Blast (radius damage + knockback), Lightning (kills in a cell,
  ignites fires/trees), Swamp (kills anyone standing in its 3×3 footprint periodically,
  bypasses shields), Firestorm.
- **Buffs on own followers** (self-cast, nearest ~6 units): Magical Shield (blocks
  spells/bolts), Bloodlust (3x damage dealt, reduced damage taken), Invisibility (hides from
  enemy auto-targeting).
- **Mind control**: Convert (wildmen → braves), Hypnotism (temporarily flips enemy units to
  caster's tribe; reverts unless the original tribe is wiped out).
- **Summons**: Angel of Death — a meteor then a creature (person type 8) that hunts the
  nearest enemy anywhere on the map, pulling victims out of buildings; ends after ~40 kills
  or ~208s. Fully modeled/functional in the exe.
- **Utility**: Teleport (sandbox-only shaman jump).

All spells go through a per-player spell book (availability states: Hidden / Discoverable /
Provided / Known / Unlimited; charges; mana cost) and a **mana economy**: mana accrues per
tribe every 16 turns from population (busy/idle followers and the shaman each contribute a
fixed amount), split between recharging training buildings, charging spells, then banking
the remainder (capped). Shaman death costs the tribe 25% of its mana and gives the killer
25%. Spell range scales with the caster's terrain altitude band plus a drum-tower bonus.

## 4. Buildings

19 modeled building types: villager hut sizes 1–3 (grows via wood investment), drum tower,
temple (trains preachers), spy/warrior/firewarrior training, "reconversion," wall, gate,
boat hut, airship/balloon hut, guard post, vault of knowledge (pyramid; grants one permanent
reward), and prison. Fixed/non-buildable structures: reincarnation site, vault, prison,
totems.

- **Huts** house and auto-breed tribespeople (brave production rate scales with occupancy
  and population band; upgradeable with wood).
- **Training huts** (warrior/firewarrior/temple/spy) consume mana to convert one entering
  follower at a time into that specialist, via a queue.
- **Vehicle huts** (boat/airship) consume wood and crew-turns to produce vehicles.
- Construction/dismantling is entirely brave-driven: flatten footprint → fetch wood → build
  up piece by piece. Buildings can be worn down by attackers or burned (fire/lightning),
  losing pieces until destroyed, leaving ashes.

## 5. Other big-picture dynamics

- **Worship economy**: separate from the mana-income system above. Totems and vaults of
  knowledge are prayed at by followers/the shaman, filling a per-site prayer gauge (fills
  faster with more simultaneous worshippers, drains when empty); a full gauge grants a
  reward (spell, building unlock, mana, or special effect).
- **Vehicles**: boats (water only) and balloons (fly anywhere, hover over obstacles) carry a
  few passengers, are built by vehicle huts, decay/"neglect" if left idle too long (explode
  or sink), and let an embarked shaman cast while being ferried into range.
- **Combat**: resolved via shared "coordinator" state machines — Challenge (approach/shove)
  escalating into Melee (ring of up to 6 fighters, scripted blow types modified by
  rank/strength/bloodlust) — plus separate logic for attacking buildings (wear-down to
  destruction), firewarrior ranged "firebolts," auto-spotting/auto-attack, and preacher
  Sermons that convert enemy units over time.
- **Coordinators as a shared primitive**: the same "coordinator" abstraction that drives
  Challenge/Melee/Sermon also underlies how spells like Convert and Hypnotism grab/affect
  units — most non-trivial exe logic is built from a handful of reusable primitives (timed
  effects, coordinators, per-kind constant tables) rather than bespoke per-feature code.

## 6. Sprite & animation file layout (original `.DAT`/`.ANI`/effect files)

Container format, **PSFB** (`pop3_format::sprites`): magic `PSFB`, a `u32` sprite count, then
one `(u16 width, u16 height, u32 offset)` per sprite (offset absolute in the file), followed
by the pixel data. Each row is RLE-coded as signed-byte commands (`0` = rest of row
transparent, `n>0` = `n` opaque palette-index bytes, `n<0` = skip `-n` transparent pixels);
index 255 is always the transparency/colour key. Little-endian throughout; not a format the
reimplementation writes, only reads (original art is never shipped).

**Sprite banks that exist in `data/`:**

| File | Sprites | Content |
|---|---|---|
| `HSPR0-0.DAT` | 7953 | people/unit body + outfit/gear elements |
| `hfx0-0.dat` | 1615 | effects, map/HUD icons, spell & building glyphs, alpha-blended VFX |
| `POINT0-0.DAT` | 162 | mouse pointers, action cursors, spell/building badge icons |
| `plspanel.spr`, `plsspace.spr` | 29, 14 | side panel artwork |
| `FONT0..2-0..2.DAT`, `font3..7-0.dat` | — | fonts |
| `MSHAD0-0.DAT`, `EDIT0-0.DAT`, `f0{0,1,2}t{0..11}-0.dat` | — | not analysed |

All share `pal0-0.dat` (256-entry RGB palette). `HSPR0-0.TAB`, the `.DAT`/`.TAB` pairs and
`vspr-0.inf` look like an older Bullfrog sprite format and are not PSFB.

**Animation tables (`data/*.ANI`)** tie sprites into unit animations:
- `VSTART-0.ANI`: 99 animations × 8 directions × 4 bytes (first frame index + a mirror-source
  index; directions 0–4 have their own frames, 5–7 mirror 3–1). Direction 0 faces the viewer,
  2 faces right, 4 shows the back.
- `VFRA-0.ANI`: one 8-byte record per frame (first element, bounding box, loop-start flag,
  next-frame index — a linked loop, not a flat array).
- `VELE-0.ANI`: one 10-byte record per sprite "element" within a frame (sprite index into
  `HSPR0-0.TAB`, x/y offset from the feet, flags for mirrored/shadow/tribe-colour
  layer/outfit layer, next-element index). Elements chain back-to-front; `AnimBank::compose_as`
  picks which layers to draw for a given tribe + outfit (brave/warrior/firewarrior/spy/preacher
  all share one body, layered; the shaman is drawn from her own, unlayered, per-tribe sprite
  set instead — only her blue/tribe-0 frames have been located in `HSPR0-0.DAT`).

**Effect/VFX sprites** live inside `hfx0-0.dat` rather than a separate bank: plain sprites
1–~1089 are HUD/map/building/spell icons and misc effects (fire 90-93, spell name banners
107-111, aerial-view building icons 115-150, panel glyphs 1028-1083, etc.); **alpha-blended
sprites** occupy two ranges, 1090–1499 and 1538–1592, where the pixel "index" is a row into a
per-theme blend table rather than a palette colour. Identified alpha effects include the
teleport dust puff, fire/explosion clouds, the volcano fireball/rock-debris burst, status
markers over people (bloodlust red bubbles, low-health sparkles, magic-shield rings,
hypnotised halo), smoke (building fire, spy arson), sparks, a water splash, wind, and parts of
a HUD cell border — many of the ~1090-1600 range are still unconfirmed by eye only.

**Blend tables** (`data/al0-X.dat`, `ghost0-X.dat`, one set per level theme, 64K entries =
256×256 palette indices) are what alpha sprites and "ghost" transparency look up into:
`al[tint*16+strength][background]` for additive/tinted alpha blending (used by the effect
sprites above), `ghost[a][b]` ≈ a 66% blend toward another colour (used for see-through/ghost
units). These are separate from — and sit underneath — the sprite banks themselves.

Net picture: **persons are flat 2D sprite animations** assembled at runtime from small
reusable element chains (body + outfit + tribe-colour layers) driven by the VSTART/VFRA/VELE
tables, while **spell/combat effects and HUD art** are a second, much larger undifferentiated
sprite bank (`hfx0-0.dat`) mixing opaque icons and alpha-blended particle-style VFX, and
**buildings/scenery are true 3D meshes**, not sprites at all (see section 2 and the
building/object findings referenced below).

## Where to go deeper

This overview is drawn from more detailed, per-topic sourced findings (units, sprites,
animations, spells, buildings, vehicles, worship, huts & training, combat, objects, trees,
and raw tuning constants) — see `AGENTS.md` for where those write-ups land. For the raw
PSFB/level file-format notes and the global asset-bank list referenced in section 6, see this
repo's `docs/file_formats` and `docs/assets_list`.

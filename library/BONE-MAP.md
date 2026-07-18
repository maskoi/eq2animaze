# EQ Skeleton Bone Map

The factory drives bones by **role**, not by guessing names. This maps every
factory role to its EQ bone name — verified present on all 28 playable models.
`build_avatar` reads `races.json` → `bones.roles` and never hard-codes a name.

## EQ bone naming convention

EQ bones use a 2-letter region prefix + part. Once you know the prefix, the whole
skeleton reads itself:

| Prefix | Region | Examples |
|--------|--------|----------|
| `pe` | pelvis / root | `pebip01`, `pepelvis`, `pebip01 tail` |
| `ch` | chest / spine | `chchest`, `chchest1`, `chchest2` |
| `ne` | neck | `neneck` |
| `he` | head | `hehead` |
| `fa` | face | `fajaw`, `faeyel/r`, `faeyelid[l/r][top/bot]`, `faeyebrow[l/r]`, `falipcorners`, `faliptop`, `falipbottom`, `fanose` |
| `bi` | bicep / clavicle / deltoid | `bibicepl/r`, `biclavl/r`, `bideltl/r` |
| `fo` | forearm | `foforearml/r`, `forobearm[l/r]1-4` |
| `fi` | hand / fingers | `fihandl/r`, `fifinger[l/r]1-2`, `fithumb[l/r]1-2` |
| `th` | thigh | `ththighl/r` |
| `ca` | calf / knee | `cacalfl/r`, `cakneel/r` |
| `bo` | foot (boot) | `bofootl/r` |
| `to` | toe | `totoel/r` |
| `*_point` | attach points (armor/weapon anchors, not deform bones) | `shield_point`, `robepoint01`… |

## Factory role → bone (identical across all families)

Every playable skeleton uses the same names for these, so the role map is shared.
The factory's clip generator and axis config key off these roles:

| Role | Bone | Driven for |
|------|------|-----------|
| `head` | `hehead` | head tracking (Head_L/R/U/D clips) |
| `neck` | `neneck` | — |
| `chest` | `chchest` | breathing idle |
| `jaw` | `fajaw` | mouth open / visemes |
| `eye_L` / `eye_R` | `faeyel` / `faeyer` | eye look clips |
| `eyelid_L/R top/bot` | `faeyelid[l/r][top/bot]` | blinks / squint |
| `brow_L/R` | `faeyebrow[l/r]` | eyebrow clips |
| `lip_corners/top/bot` | `falipcorners` / `faliptop` / `falipbottom` | mouth shapes |
| `nose` | `fanose` | nose clips |
| `bicep_L/R` | `bibicep[l/r]` | arms-down rest pose |
| `forearm_L/R` | `foforearm[l/r]` | — |
| `hand_L/R` | `fihand[l/r]` | hand clips |
| `thigh/calf/foot/toe _L/R` | `ththigh` / `cacalf` / `bofoot` / `totoe` | **stance (from p01)** |
| `tail` | `pebip01 tail`..`tail4` | tail idle (Iksar / Vah Shir only) |

## Per-family facts

| Family | Bones | Tail | Members |
|--------|-------|------|---------|
| ELM | 104 | no | Human, Barbarian, Erudite, Wood Elf, High Elf, Dark Elf, Half Elf (M) |
| ELF | ~109 | no | same races (F) |
| DWM / DWF | 95 / 101 | no | Dwarf, Halfling, Gnome |
| OGF | 92 | no | Troll, Ogre |
| IKM | 105 | **5-segment** | Iksar M/F |
| KEM / KEF | 108 / 98 | **5-segment** | Vah Shir M/F |

The tail is a chain parented to `pebip01`: `pebip01 tail` → `tail1` → … → `tail4`.
Only Iksar and Vah Shir have it — so it's the one role the factory must treat as
optional; everything else is guaranteed present.

## Why this is bulletproof

`races.json` records, per race: the exact bone name for every role, a
`critical_missing` list (empty for all 28), and `has_tail` / `tail_segments`. A new
build starts from verified names — it can't drive a bone that isn't there, and it
knows in advance whether to author tail motion. No per-race spelunking, ever.

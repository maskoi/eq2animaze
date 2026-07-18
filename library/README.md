# eq2animaze Model Library

The factory's parts catalog. Every playable EverQuest race, extracted once with a
**patched LanternExtractor** that recovers the animations Lantern normally drops,
then documented so `build_avatar` can look a race up by code and never touch model
guts again.

## Why this exists

Stock LanternExtractor silently discards animations for any model whose track
names carry a **variant letter** (`C01`**`A`**`IKM...` instead of `C01ELM...`) —
which is every Kunark-and-later race, Iksar included. Our patched build recovers
them. See [../docs/LANTERN-ANIMATION-FIX.md](../docs/LANTERN-ANIMATION-FIX.md).

With animations in hand, every race ships its **real in-game stand pose (`p01`)** —
so stance, feet, knees, and arms come from Norrath, not from hand-guessed rotations.

## Skeleton families (who shares animations)

EQ's own `animationsources.txt` clusters all races into a handful of skeleton
families. Races in a family share bone structure, so **one animation clip set
covers the whole family**:

| Family | Base | Races |
|--------|------|-------|
| Elf-M / Elf-F | ELM/ELF | Human, Barbarian, Erudite, Wood Elf, High Elf, Dark Elf, Half Elf (M+F) |
| Dwarf | DWM/DWF | Dwarf, Halfling, Gnome (M+F) |
| Ogre | OGF | Troll, Ogre (M+F) |
| Iksar | IKM | Iksar M+F (+ Iksar citizens/skeletons) |
| Vah Shir | KEM/KEF | Vah Shir M+F |

## EQ animation codes (the clip vocabulary)

Every race uses the same 3-char animation naming. The ones the factory cares about:

| Code | Meaning | Factory use |
|------|---------|-------------|
| `p01` | **passive stand / idle** | **THE rest/export stance** — correct feet |
| `p02`–`p09` | other passive (sit, crouch, etc.) | optional idles |
| `l01`–`l12` | locomotion (walk, run, jump, swim) | idle motion / breathing source |
| `c01`–`c11` | combat swings | — |
| `s01`–`s29` | social / emotes | optional |
| `d01`–`d05` | damage / death | — |
| `t04`–`t09` | misc | — |

Suffix `a`/`b` = animation variant (a = primary).

## Files

- `races.json` — machine-readable catalog: per race, the GLB path, skeleton family,
  bone/joint count, animation count, and the full clip list. `build_avatar` reads this.
- `MODELS.md` — human-readable table of everything extracted.

## Usage (the whole point)

```jsonc
// a race config just names the code; the library supplies the rest
{ "race": "ikm" }   // -> library resolves glb, bones, p01 stance, clip set
```

No more opening archives, decoding WLD strings, or guessing bone axes per race.
The library did that once, wrote it down, and closed the hood.

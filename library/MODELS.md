# EQ Model Roster

All 28 playable models, extracted with the patched LanternExtractor and fully bone-mapped. See [BONE-MAP.md](BONE-MAP.md) for the role table.

- **stance** = in-game `p01` stand pose, used as the export stance (correct feet/knees/arms)
- **anim** = native clip count, or borrows its bone-matched family base
- **tail** = segments (Iksar / Vah Shir only)

| Code | Race | Family | Bones | Tail | Anim | Stance | Crit-OK |
|------|------|--------|-------|------|------|--------|--------|
| `hum` | Human | ELM | 104 | - | 141 | `p01a` | yes |
| `huf` | Human F | ELF | 110 | - | 143 | `p01a` | yes |
| `bam` | Barbarian | ELM | 104 | - | 145 | `p01a` | yes |
| `baf` | Barbarian F | ELF | 101 | - | 139 | `p01a` | yes |
| `erm` | Erudite | ELM | 104 | - | borrows elm | `p01a` | yes |
| `erf` | Erudite F | ELF | 109 | - | borrows elf | `p01a` | yes |
| `elm` | Wood Elf | ELM | 104 | - | 131 | `p01a` | yes |
| `elf` | Wood Elf F | ELF | 109 | - | 131 | `p01a` | yes |
| `him` | High Elf | ELM | 104 | - | borrows elm | `p01a` | yes |
| `hif` | High Elf F | ELF | 109 | - | borrows elf | `p01a` | yes |
| `dam` | Dark Elf | ELM | 104 | - | borrows elm | `p01a` | yes |
| `daf` | Dark Elf F | ELF | 109 | - | borrows elf | `p01a` | yes |
| `ham` | Half Elf | ELM | 104 | - | borrows elm | `p01a` | yes |
| `haf` | Half Elf F | ELF | 109 | - | borrows elf | `p01a` | yes |
| `dwm` | Dwarf | DWM | 95 | - | 137 | `p01a` | yes |
| `dwf` | Dwarf F | DWF | 101 | - | 135 | `p01a` | yes |
| `trm` | Troll | OGF | 92 | - | 135 | `p01a` | yes |
| `trf` | Troll F | OGF | 93 | - | 135 | `p01a` | yes |
| `ogm` | Ogre | OGF | 92 | - | 137 | `p01a` | yes |
| `ogf` | Ogre F | OGF | 101 | - | 136 | `p01a` | yes |
| `hom` | Halfling | DWM | 96 | - | 138 | `p01a` | yes |
| `hof` | Halfling F | DWF | 101 | - | 136 | `p01a` | yes |
| `gnm` | Gnome | DWM | 104 | - | 138 | `p01a` | yes |
| `gnf` | Gnome F | DWF | 109 | - | 131 | `p01a` | yes |
| `ikm` | Iksar | IKM | 105 | 5 | 141 | `p01a` | yes |
| `ikf` | Iksar F | IKM | 106 | 5 | 145 | `p01a` | yes |
| `kem` | Vah Shir | KEM | 108 | 5 | 154 | `p01a` | yes |
| `kef` | Vah Shir F | KEF | 98 | 5 | 142 | `p01a` | yes |

**All 28 models pass critical-bone verification.** 20 carry native animation sets; 8 skin-variants borrow bone-matched family clips.

# eq2animaze

Turn classic EverQuest character models into fully working [Animaze](https://www.animaze.us/) VTuber avatars — bone-driven face tracking, visemes, idle animation, authentic textures — in about 35 seconds per build.

Born from **Maskoi** ("Ironscales"), a 105 Iksar Warrior of Cazic-Thule, rebuilt as a live avatar after ~55 versions of trial, error, and hard-won pipeline law.

## What it does

```
python source/pipeline/eq2animaze.py config_maskoi.json V56
```

One command takes a LanternExtractor-exported character GLB + armor texture tiles and produces an import-ready Animaze package:

- Single-material **texture atlas** (Animaze's FBX importer applies only one texture per mesh)
- **144 bone-animation clips** discovered by filename — full FaceRig-heritage face set (blinks, visemes, brows, jaw, tongue, hands) with zero blendshapes
- Grounded, human-scaled, planted stance
- Post-processed colors via Pillow (Blender cannot ship correct pixels — Law 4)

## The Five Laws

Violate any one and the avatar breaks. See [docs/PIPELINE-PLAYBOOK.md](docs/PIPELINE-PLAYBOOK.md):

1. One texture per mesh → bake an atlas
2. Never ship blendshapes → bone clips only
3. Never use Animaze-recognizable bone names → keep EQ names
4. Blender cannot ship correct texture colors → postprocess every pixel
5. Every clip's frame 1 = the shared rest pose, families byte-identical

Plus the root-cause discovery: **EQ swaps the X and Y axes** (verified in MQ2 source and LanternExtractor's conversion code), which is why imported bone axes can never be trusted from theory — lab each bone empirically, freeze axis+sign in the config.

## What's NOT here

No EverQuest game assets. Extract your own with [LanternExtractor](https://github.com/LanternEQ/LanternExtractor) from a client you own. The `.gitignore` enforces this — models, textures, and archives never enter this repo.

## Docs

- [docs/PIPELINE-PLAYBOOK.md](docs/PIPELINE-PLAYBOOK.md) — the formula: laws, build stages, verified bone-axis table, per-avatar checklist
- [docs/CODEX-HANDOFF-50-VERSIONS.md](docs/CODEX-HANDOFF-50-VERSIONS.md) — the war story: every landmine and how it was found

## Requirements

- Blender 4.5+ (headless build)
- Python 3.10+ with Pillow (color postprocess)
- LanternExtractor exports of your own EQ client
- Animaze Editor (import as **Standard**, never ARKit)

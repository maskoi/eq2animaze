# Build an EverQuest → Animaze Avatar — Step by Step (for Codex)

**Goal:** turn an EverQuest character into a working Animaze VTuber avatar — matte scaly skin,
feet planted flat, live face-tracking, correct armor/clothing look. Follow these steps *exactly*;
the pipeline already encodes every hard-won fix. Do **not** improvise the rig or the shader.

Full reference: `docs/PIPELINE-PLAYBOOK.md` (read "THE APPEARANCE RECIPE" + "MANDATORY DEFAULTS").
This file is the short, executable version.

---

## 0. Prerequisites (verify before you start)
- Blender 4.5 → `C:\Program Files\Blender Foundation\Blender 4.5\blender.exe`
- Pipeline root → `C:\Users\Raphael\Desktop\Maskoi Avatar\eq2animaze\`
- System Python 3 with **Pillow** (used by the color post-process; Blender's Python is NOT used for it)
- Base rig present → `source/assets/base-iksar/ikm.glb` (Iksar; full skeleton)

## THE TWO NON-NEGOTIABLE RULES
1. **RIG comes from the base race model** (`source/assets/base-iksar/ikm.glb`). It has the full
   skeleton (`fajaw`, `bofootl`, `bibicepl`, `hehead`…). **NEVER** set `base_glb` to a textured
   equipment export like `global4/ikm.glb` — those are stripped meshes (~40 nodes, no animation
   bones) and produce a crumpled grey gremlin with zero animations.
2. **The LOOK is a texture SWAP onto that rig**, driven by config — never by changing the base model.

---

## 1. Choose (or copy) a config
Configs live in `source/pipeline/`. Two proven starting points:

| Config | Look |
|--------|------|
| `config_iksar_naked.json` | bare scaled skin (`armor_parts: []`) |
| `config_maskoi_harness.json` | harness + loincloth + bare-scaled legs |

The texture swap is controlled by three fields:
```jsonc
"base_glb":        "source/assets/base-iksar/ikm.glb",     // ALWAYS the base rig
"armor_tiles_dir": "source/assets/global4-iksar/Textures", // folder of the look's tiles
"armor_set":       "00",                                    // EQ material #: 00 naked/cultural, 04 plate
"armor_parts":     ["ch","lg","ua","fa","ft","hn"]          // which body regions to swap (omit "he" = keep natural head)
```
The remap matches `d_ikm(part)sk(NN)` → tile `ikm(part)(SET)(NN).png` in `armor_tiles_dir`.

## 2. Build (Blender, headless)
Set two env vars, run `build_avatar.py`. Example (git-bash / POSIX):
```bash
cd "C:/Users/Raphael/Desktop/Maskoi Avatar/eq2animaze"
export EQ2ANIMAZE_CONFIG="source/pipeline/config_maskoi_harness.json"
export EQ2ANIMAZE_OUTNAME="Maskoi-Harness-V3"        # ALWAYS a NEW name (Animaze caches by name)
"/c/Program Files/Blender Foundation/Blender 4.5/blender.exe" --background --python source/pipeline/build_avatar.py
```
Output lands in `work/IMPORT-ONLY-<OUTNAME>/`.

## 3. Post-process the textures (MANDATORY — Law 4)
Blender cannot ship correct colors; the raw atlas is dark. Fix it with system Python + Pillow:
```bash
python source/scripts/postprocess_textures.py "work/IMPORT-ONLY-Maskoi-Harness-V3"
```
Expect: `Maskoi_Body_Atlas.png: composed body atlas from manifest`.

## 4. Sanity-check the build (do NOT render after every step)
```bash
WORK="work/IMPORT-ONLY-Maskoi-Harness-V3"
ls "$WORK/$EQ2ANIMAZE_OUTNAME.fbx"            # FBX exists
ls "$WORK/Animations" | wc -l                # ~144 clips (a broken rig gives ~68 or fewer)
ls "$WORK/Textures/Maskoi_Body_Atlas.png"    # full-size atlas (2048x1024, not 2048x512)
```
Optional: ONE checkpoint render if you want eyes on it — never a render after every stage.
**Renders can lie; the Animaze app is the only truth.**

## 5. Import into Animaze
1. Animaze Editor → import `work/IMPORT-ONLY-<OUTNAME>/<OUTNAME>.fbx`.
2. Choose **STANDARD** import mode (NOT ARKit — this build uses bone clips, not blendshapes).
3. Dismiss the one benign **"Head bone was not found"** dialog (it's protective; keep pure EQ bone names).
4. **Snap to Ground** → **Save.** (This plants the feet on the floor and persists it — do not
   try to fix floating in the pipeline; Snap to Ground is the intended step.)

## 6. Test in the app
- **Your face drives him:** open mouth → jaw drops; blink → eyes close; turn head → head follows.
- Skin is **matte, not glassy**; **feet planted flat**; arms hang at sides (Animaze applies the
  arms-down clip on load — T-pose in the static file is normal).
- Import log has no red **errors** (a `fajaw ROTATION differences` warning is a known non-fatal nag).

---

## The defaults you inherit automatically (D1–D7, hard-coded in `build_avatar.py`)
D1 matte hide (Metallic 0.0) · D2 EQ o01 idle foot pose (heel-down flat) · D3 arms-down ·
D5 opaque blend · D6 post-process every build · D7 jaw reference frame.

## Walls we already hit — do NOT repeat them
- **Textured export as base** → grey gremlin, no animations. Use the base rig + texture swap.
- **Metallic > 0** → "made of glass" + washed skin. Skin is matte.
- **Single-axis `foot_flat`** → only toe-pads plant, heel stays up. Use the baked EQ foot pose (D2).
- **Floating on import** → Snap to Ground in Animaze, not a pipeline offset.
- **Re-using an OUTNAME** → Animaze serves the cached old build. Always a new name.

## Deliverable to hand back
`work/IMPORT-ONLY-<OUTNAME>/<OUTNAME>.fbx` + its `Textures/` and `Animations/` folders, plus the
Animaze import log and one front screenshot from the app (per the "PROVEN" definition in the playbook).

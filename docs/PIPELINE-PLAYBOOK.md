# EQ → Animaze Avatar Pipeline Playbook
*The formula, distilled from Maskoi V1–V50 (2026-07-17). Read this before building any new avatar.*

Current gold build: `source/scripts/build_maskoi_V50_polish.py` + `source/scripts/postprocess_textures.py`

## IMPORT MODE — the one rule (supersedes all older "never ARKit" wording)
**Import as STANDARD unless the specific build was made for ARKit.**
- **STANDARD** = bone-driven face clips (the proven default). Ships NO blendshapes.
- **ARKit** = blendshape/morph-target face. Only for builds that deliberately ship
  ARKit-named shape keys (`jawOpen`, `eyeBlinkLeft`, …). A Standard build imported as
  ARKit has no face; an ARKit build imported as Standard fires blendshapes on autoblink.
- Match the import mode to what the FBX actually carries. This is a per-build decision,
  not a blanket ban. (Earlier docs said "never ARKit" — that was true while we only
  shipped bone clips; it is superseded now that the ARKit shape-key path is in play.)
Protocol: Animaze Editor → Avatar3D → **[STANDARD or ARKit per the build]** → Snap to ground → Save → Bundle.

## DEFINITION OF "PROVEN" (do not call anything proven until all four)
For this project, "proven" / "confirmed working" means, strictly:
1. Imported **fresh** into Animaze (new folder + FBX basename — caching lies otherwise),
2. **Import log attached** (no unexpected errors),
3. **Screenshots attached** (front / side / face as relevant),
4. **Visual QA passed** by a human looking at the actual app.
Anything short of that is a **candidate**, not proven. A clean Blender render, a passing
integrity check, or "the log looks fine" prove references exist — NOT that it looks right.
(Renders can lie; the app is the only truth. Learned repeatedly.)

---

## THE FIVE LAWS (violate any one and the avatar breaks)

1. **Animaze applies only ONE texture per mesh** (slot 0's, stretched over everything).
   → Bake all body-region textures into a single atlas (2048×1024, 8×4 grid of 256px cells,
   16px edge-replicated gutters, UV inset 16/256), one material, one mesh.
   Extra meshes are fine if each is single-material (greaves are).

2. **Never ship blendshapes.** Animaze's FBX-2018 runtime corrupts the face whenever a
   Blender-exported morph fires (black flickering polys). Face = **bone animation clips**
   discovered by NAME from the `Animations/` folder (FaceRig heritage). Zero shape keys.

3. **Never use Animaze-recognizable bone names.** `BipHead`/`BipLEye`/`Head`-style names let
   look-at-camera procedurally rotate bones with standard-rig axis assumptions — on EQ rigs
   the eyes roll into the skull and the head folds inside-out. Keep pure EQ names
   (`hehead`, `faeyel`…). Cost: one benign "Head bone was not found" dialog per import.

4. **Blender cannot ship correct texture colors.** `image.save()` = raw linear dump (dark);
   `save_render()` = view-transform contaminated. All shipped pixels come from
   `postprocess_textures.py` (system Python + Pillow), run after EVERY build.

5. **Every clip's reference frame must match.** Frame 1 of every clip = the shared rest pose
   (validated against `idle1`). Pose clips ramp: frame 1 = rest, frames 8–16 = held.
   Family rule: `MouthOpen_*` variants are validated against `MouthOpen` — any bone they
   share with the parent clip must carry the IDENTICAL curve (e.g. jaw 0.35 everywhere).

---

## BUILD PIPELINE (stages in the V50 script)

1. Import base glb (LanternExtractor output) → delete junk `Icosphere` → fold UVs to 0..1.
2. Armor: swap each body material's texture image to its armor-set tile
   (`ikm(part)(SET)(tile)` — set 04 = plate). Tiles in `source/assets/plate-set04/`.
3. Greave/boot `.mod` pieces: weight-transfer from the **EVALUATED (posed)** body
   (raw bind coords are inverted — bind-space matching straps armor to the skull/face).
4. Atlas bake: manifest → cells → single material; `atlas_manifest.json` written for postprocess.
5. Shape section: **empty** (Law 2).
6. Animation clips (all exported as separate FBX per clip; exporter honors real clip length,
   `frame_end = max(16, action.frame_range[1])`):
   - Required tree: `Head_L/R/U/D/Twist_*`, `Avatar_*`, `LeftEye_*/RightEye_*`, `MouthJaw_L/R`,
     ears, hands, fingers, tongue-directionals.
   - `idle1` = slow breath: chchest axis2 0.012 over 96 frames (never 16-frame sway = wobble).
   - `idle_naturalPose_L/R` = arms-down rest ramp: **bibicepl/bibicepr axis 2, ∓0.95**
     (delt bones are decorative spikes, do nothing).
   - Face clip set (~60 clips): see axis table below.
7. Pose determinism: snapshot after action-restore@frame1, `restore_pose()` before save/export.
8. Grounding: lift armature so lowest evaluated vertex = z 0 (Maskoi: +4.005).
9. Postprocess: compose atlas (authentic tiles verbatim + alpha flattened — EQ hides an
   env-shine mask in armor alpha that renders black; flat 8×8 tiles are white TINT CANVASES —
   fill with the part's detailed-tile mean, or dye), then package under a NEW folder+FBX name
   (Animaze caches by name).

## VERIFIED BONE AXES (Maskoi rig — re-lab per new rig!)

| Motion | Bone(s) | Axis | Amount |
|---|---|---|---|
| Jaw open | fajaw | 0 | **−0.35** (V53: Blender lab shows +0.35 = down, but Animaze plays it INVERTED — user saw jaw go up into head. Ship negative. All jaw-open literals derive from config via `JW()` so one config sign flips the whole viseme family) |
| Jaw lateral | fajaw | 2 | ±0.10 |
| Eyelid close | faeyelid(l/r)top | 0 | +1.1 (bot: −0.5) — NOT inverted in-app (blinks verified live) |
| Arms down | bibicep(l/r) | 2 | ∓0.95..1.1 |
| Feet flat (stance) | bofoot(l/r) | 0 | **∓0.75 MIRRORED like arms** (l neg / r pos). V53: GLB static pose hangs feet en pointe = the "flying, toes-down" look. Config `foot_flat`. Baked into the REST pose (apply armature mod to meshes → `pose.armature_apply`) because pose-bone rotations never reach the FBX bind pose |
| Breath | chchest | 2 | 0.012 / 96f |
| UNVERIFIED (plausible guesses shipped in V49/V50) | brows (faeyebrow*), lips (falip*), nose (fanose) | 0/1/2 | 0.1–0.5 |

**THE ROOT CAUSE (user insight 2026-07-17, verified in source):** EQ's engine axes are
unconventional — `/loc` prints `Y, X, Z` (MQ2Commands.cpp:1271) and facing math is
`atan2(ΔX, ΔY)` (MQ2Commands.cpp:1704). LanternExtractor then converts to glTF at the bone
level by component-swizzling quaternions `(x, y, z, w) → (x, z, −y, w)` and translations to
`(x, z, −y)` (GltfWriter.cs `ApplyBoneTransformation`, ~line 724) — a proper −90° X rotation,
NOT a mirror — while mesh geometry travels a different-looking path with an X reflection.
(Bonus: Lantern multiplies all four quat components incl. W by π/180 then normalizes — a
no-op that only works by accident. That's the code quality underneath us.) Blender's glTF
import and Animaze's FBX SDK each stack their OWN up-axis conversions on top. The conversion
SEAM between these five remaps is why: the rig faces +X, bone local frames are per-rig alien,
bind-vs-pose never lined up, and a rotation can be correct in Blender yet play INVERTED in
Animaze (the jaw). Rule: imported local axes can never be trusted from theory — lab each
important bone in Blender, confirm once in Animaze, save axis+sign in the config. If in-app
plays inverted vs Blender: flip the config sign, don't re-lab, don't "fix" the model globally.

**Lab traps learned in V53:** (1) judge pitch/hinge axes from a SIDE profile render — front
views are ambiguous (fooled us on both jaw and feet). (2) L/R limb bones MIRROR signs —
rotating both feet the same sign sends one up and one down and every render looks confusingly
"unchanged". (3) Bone head→tail pitch math is garbage on EQ rigs — GLB import auto-generates
tails; only bone HEAD positions are real. (4) The `ImportLog.log` "Check clip reference
frame … fajaw has ROTATION differences (4.05°)" spam on MouthOpen_* is BENIGN — the shipped
FBX curves are byte-identical (verified by re-importing the clip FBXs and dumping f-curves);
it's Animaze sampling noise on the ramp, present since V50, avatar works fine.

**Axis lab method** (the only reliable way): open built blend → clear armature action
(fcurves override manual pose!) → rotate candidate bone each axis ± → textured tight
close-up renders (repoint texture nodes at the shipped `Textures/` PNGs — reopened blends
lose generated pixels) → pick visually.

## PER-NEW-AVATAR CHECKLIST

1. Extract race glb: LanternExtractor, `global<race><sex>_chr.s3d` (e.g. `globalikm`).
   Raw-dump the archive too — armor texture sets (`00-04` classes, `10-16` Velious robes)
   only exist in the raw dump. Head/helm variants may live in `global4_chr.s3d` (HE00-03).
2. Convert chosen armor set tiles → PNG assets folder; update the swap-regex part list.
3. Update all bone names in the script if the rig differs (facial bone names are per-model).
4. **Re-run axis labs** — every rig's bone frames are different alien nonsense.
5. Adjust ground-lift (auto-computed), skull-anchoring constants if transplanting a helm.
6. Fresh folder/FBX name per import attempt. Import Standard. Expect + ignore:
   head-bone dialog, eye-range-zero dialog, flat-idle1 info, new-brow-set warnings.

## PARKED / TODO

- Eyebrow/lip/nose clip axes unverified (shipped conservative guesses) — lab + tune.
- `HandL_closeUp_Mid` satisfied in V50; watch for further closeUp family asks (R/U/D…).
- Helm: authentic `IKMHE03` mesh extracted (`Exports/global4/Characters/ikm_03.glb`),
  transplant recipe proven in V14 (dome-anchored seat, pitch −30, double-sided, dyed) —
  re-add as its OWN single-material mesh when wanted.
- Teal armor variant: `_colorize()` luminance dye in postprocess (TEAL_LIN/LUM_FLOOR/LUM_GAIN).
- AnimationRetargetingConfig in the generated .item is disabled → no generic Animaze
  idles/specials; enable+map later via Editor retargeting panels if wanted.
- Bundle final: hash, version label, per handoff definition-of-done.

## EXTRACTION TOOLS LANDSCAPE (researched 2026-07-17)

- **[LanternExtractor](https://github.com/LanternEQ/LanternExtractor)** (C#) — our current tool; best-in-class for Trilogy S3D/WLD→glTF. Known bugs we work around: gequip2 texture-folder ordering; exports only the primary head variant (heads live in global4_chr).
  Forks: [vermadas/LanternExtractor](https://github.com/vermadas/LanternExtractor).
- **[quail](https://github.com/xackery/quail)** (Go, xackery) — modern PFS/EQG/S3D manager, actively maintained, plus **[quail-addon](https://github.com/xackery/quail-addon)**: native Blender import of .eqg/.s3d. STRONG candidate to replace our extract step — direct-to-Blender kills the glb intermediary.
- **[eqsage](https://github.com/knervous/eqsage)** (knervous) — modern EQG/S3D converter + viewer with glTF export, even runs in-browser ([eqsage.vercel.app](https://eqsage.vercel.app/)). Good for quick visual asset browsing before committing to a build.
- **[libeq](https://github.com/cjab/libeq)** (Rust) — clean-room WLD/S3D format libraries + CLIs (`s3d`, `wld-cli`). **v0.5.1 released 2026-03-02** with prebuilt Windows binaries; round-trips S3D/PFS and WLD fragments to JSON/RON. TWO roles for us:
  1. **Validation instrument NOW**: dump any WLD to JSON and verify raw structures (head variants, bone weights, fragment layouts) without trusting LanternExtractor's interpretation — would have shortcut several of our archaeology digs.
  2. **Parser foundation LATER**: the base layer if we build a native eq→Blender importer (it doesn't do character-to-Blender itself).
- **[EQZip](https://github.com/Shendare/EQZip)** — S3D/EQG/PFS/PAK archive GUI manager (texture-level edits).
- Legacy (avoid): WLD Editor Suite, OpenEQ, 2000s-era OBJ rippers — superseded.

**Own-tool verdict:** don't rewrite extraction — quail + libeq already cover it. The gap worth
owning is the THIS pipeline: a single `eq2animaze` CLI wrapping extract → build → postprocess →
package with per-race config files. Our Blender+Python scripts are 90% of it already; the tool
is mostly packaging what this playbook describes.

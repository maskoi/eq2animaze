# Codex Handoff: How Maskoi Took 50 Versions — Everything Learned
*Written by Claude (Opus 4.8) for Codex, 2026-07-17, after a single marathon session V9→V51.*
*Companion docs: `PIPELINE-PLAYBOOK.md` (the formula), `source/pipeline/` (the factory).*

## TL;DR

Raphael's EverQuest Iksar warrior **Maskoi** (in-game: Ironscales, 105 WAR) is now a fully
working Animaze avatar: authentic body/face/armor, head tracking, blinking, bone-driven
lipsync with full viseme set, arms at rest, breathing idle, human-scale, grounded.
Current build: `work/IMPORT-ONLY-Maskoi-Armored-V51/`.
The whole pipeline is now one command: `python source/pipeline/eq2animaze.py config_maskoi.json` (~30s).
**Import protocol: Animaze Editor → Avatar3D → STANDARD (never ARKit) → Snap to ground → Save → Bundle.**

## Why it took 50 versions: the five buried landmines

Every one of these was invisible, undocumented, and mimicked other bugs. In discovery order:

### 1. Animaze applies only ONE texture per mesh (found V22→V23)
Its 2018-era FBX importer takes material slot 0's texture and stretches it across the whole
mesh. Every multi-material build (V1–V22) was secretly rendering ONE texture through 30
materials' UV islands. This retroactively explained *everything* from before this project:
"V6's perfect skin" = a leg texture tiled everywhere; "V8's armored face" = an atlas landing
on face UVs. **Fix: bake all body textures into a single 2048×1024 atlas (8×4 grid, 256px
cells, 16px edge-replicated gutters against mip bleed, UV inset 16/256), ONE material.**
Extra meshes are fine if single-material each.

### 2. Blender cannot export correct texture colors (found V11→V13)
`image.save()` writes raw linear floats (everything dark); `save_render()` bakes the scene's
AgX view transform + exposure into the file (everything washed). Every build ever shipped
distorted pixels. **Fix: Blender never touches shipped pixels — `postprocess_textures.py`
(system Python + Pillow) rewrites the Textures/ folder after every build: authentic tiles
verbatim, dyes done in explicit sRGB math.** Bonus traps: EQ armor textures hide an
env-shine mask in ALPHA (flatten to 255 or it renders black); EQ's flat 8×8 tiles are white
TINT CANVASES (fill or dye them, or you get white patches at neck/shoulders).

### 3. Animaze look-at-camera destroys nonstandard rigs (found V41→V43)
Once bones were named `BipHead`/`BipLEye`/`BipREye` (to silence the "Head bone was not
found" dialog), the look-at behavior started procedurally rotating them assuming standard
axis conventions. On the EQ rig's alien bone frames: eyeballs rolled INTO the skull, and in
the app the head folded inside-out (giant black face void). **Fix: keep pure EQ bone names
(`hehead`, `faeyel`…) so look-at finds nothing. The nag dialog is a shield — click OK.**
Head tracking never needed look-at; it runs through the `Head_L/R/U/D` animation clips.

### 4. Blendshapes corrupt the face at runtime (found V45 — THE big one)
Blender-exported FBX morphs break Animaze's renderer whenever a shape fires (the app fires
autoblink/idle constantly; the Editor doesn't — which is why the Editor always looked fine
while the app showed "blinking black tiles" since forever). Proven by V45-NOSHAPES:
zero shape keys → face rendered perfectly in the app. **Fix: NO blendshapes, ever. The face
is driven by BONE ANIMATION CLIPS discovered by filename from Animations/ (FaceRig
heritage): `MouthOpen.fbx`, `LeftEyeClosed.fbx`, all 18 visemes, etc. This requires
importing as STANDARD — ARKit mode is blendshape-only and ignores clip faces.**

### 5. Everything about EQ data is in a different coordinate space than you think
- The rig's BIND pose is inverted vs its posed appearance (head at leg height). Consequences:
  - Armor `.mod` weight transfer must match against the EVALUATED (posed) body — bind-space
    matching strapped the greaves to the HEAD and FACE bones (hidden since V9; exploded into
    giant planks the moment the arms-down pose actually played).
  - Shape deltas authored in world directions crumple faces when applied to bind-space verts.
  - Any helm/armor transplant must freeze evaluated world coords first.
- The model is ~7m tall in export units → Animaze dangles it by the head ("flying, toes
  down"). Fix: `global_scale` normalization to `target_height_m` (2.1 for Iksar).

## The animation rules Animaze enforces (learned the hard way)

- Every clip's frame 1 must match the shared rest pose (validated against `idle1`).
- Family rule: `MouthOpen_*` variants are validated against `MouthOpen` — shared bones must
  carry IDENTICAL curves (all jaw channels = 0.35).
- Pose clips (naturalPose, face poses) RAMP: frame 1 = rest, frames 8–16 = held.
- `idle1` loops forever: 16-frame sway = seasickness; flat = statue; correct = one gentle
  96-frame breath (chchest axis2, 0.012 rad).
- Arms-down rest = `idle_naturalPose_L/R` posing the BICEPS (`bibicepl/r` axis 2, ∓0.95);
  the "delt" bones are decorative shoulder-spike bones with almost no weights.
- The animtree asks for families by name; feed it and warnings vanish
  (`HandL_closeUp_L/Mid/R`, `LeftEyeClosed_Squint`, nose set, viseme set).

## Verified bone axes (Maskoi rig — re-lab for each new rig)

| Motion | Bone | Axis | Amount |
|---|---|---|---|
| Jaw open | fajaw | 0 | +0.35 |
| Jaw lateral | fajaw | 2 | ±0.10 |
| Blink | faeyelid(l/r)top / bot | 0 | +1.1 / −0.5 |
| Arms down | bibicep(l/r) | 2 | ∓0.95 |
| Breath | chchest | 2 | 0.012 over 96f |

Axis-lab method: open built blend → **clear the armature action first** (fcurves override
manual posing) → rotate candidate axis ± → textured tight close-up render (repoint texture
nodes at shipped Textures/*.png — reopened blends lose generated pixels) → judge visually.

## Asset knowledge (Iksar; the pattern generalizes)

- Base model: `globalikm_chr.s3d` → LanternExtractor → `ikm.glb` (body+eyes only; contains a
  junk 42-vert Icosphere — delete it).
- Old-model armor = per-region texture tile swaps: `ikm(ch|lg|ft|hn|ua)(SET)(tile)`;
  sets 00–04 = armor classes (04 = plate = the Ironscales base), 10–16 = Velious quest robes
  (chest/arms/face only). Tiles only exist in the RAW archive dump. `velious_plate_ikm_c.dds`
  is the atlas for the it238xxx.mod GEOMETRY pieces (greaves/boots), NOT body texture.
- Head/helm variants (HE00–HE03 incl. the flared "Batman" plate helm) live in
  `global4_chr.s3d` → `ikm_03.glb`. Helm transplant recipe proven in V14: strip to materials
  tm_ikmhe0010/13/14, freeze evaluated coords, skull-anchor (rear-x/top-z/center-y, width
  scale), pitch −30° about skull center, dome-anchored seat, double-side faces, dye, rigid
  bind to hehead. Parked — re-add as its OWN single-material mesh.
- In-game teal = tint over the textures. Authentic-undyed is the current ship; the
  `_colorize()` luminance dye (TEAL_LIN/LUM_FLOOR/LUM_GAIN knobs) exists in postprocess.

## The factory

```
source/pipeline/
  eq2animaze.py       # one command: validate → Blender build → postprocess → package (~30s)
  build_avatar.py     # generalized build (all laws encoded), driven by env-passed config
  config_maskoi.json  # reference config: paths, race_token, armor set/parts, greaves, axes, target_height_m
```
New character = copy config, point at new race assets, run. Re-lab axes only if the face/arms
misbehave. Every import needs a fresh package name (Animaze caches by name) — the runner
auto-tags with a timestamp.

## Expected benign import noise (do not chase these again)
- "Head bone was not found" (look-at disarmed — intentional)
- "eye/head range is 0" wall (same)
- "animations without any movement: idle1" (only if idle is flat)
- "Blendshape LeftBrowUp… not found" (new-brow set intentionally not shipped; classic set is)
- "HandL_closeUp_X missing" (feed the name it asks for, one clip each)

## Open items
- Eyebrow/lip/nose clip axes are conservative first-guesses — lab + tune per feedback.
- Helm (IKMHE03) re-integration, blue forehead gem (purple-blue emissive ico on dome front).
- AnimationRetargetingConfig disabled in the .item → no generic Animaze idles/specials;
  map via Editor retargeting panels if wanted someday.
- Tools: prefer quail (xackery) / eqsage (knervous) / libeq (cjab) over legacy extractors;
  LanternExtractor remains fine. Don't rewrite extraction — own the eq2animaze layer instead.
  **libeq update (verified): v0.5.1 released 2026-03-02, prebuilt Windows binaries, S3D/PFS +
  WLD ⇄ JSON/RON round-trip.** Use `wld-cli` as a validation instrument (dump fragments to
  JSON to verify head variants/weights/structures instead of inferring through Lantern), and
  as the parser foundation if a native eq→Blender importer is ever built.

## V53 addendum (jaw + stance, 2026-07-17)

Two live-test bugs from V51/V52 and their fixes — both were AXIS-LAB TRAPS:

1. **Jaw opened UP into the head.** Blender lab genuinely shows fajaw axis0 +0.35 = open
   DOWN (verified again in profile renders), but Animaze plays that same curve INVERTED.
   Blinks are NOT inverted (verified live). Fix: config `jaw_open.amount: -0.35`; every
   jaw-open literal in build_avatar.py now derives from config via `JW()` (fractions of the
   configured open), which also guarantees the MouthOpen_* family carries byte-identical jaw
   curves (Law 5) no matter how the amount is tuned later.
2. **"Flying, toes-down" stance.** The GLB ships no animations — its static node pose IS the
   rig's rest pose, and that pose hangs the feet en pointe (ankle→toe pivot nearly vertical,
   −88°). Two sub-traps: (a) L/R foot bones MIRROR signs exactly like the arms (bofootl
   NEGATIVE / bofootr POSITIVE axis0 plants both feet; same-sign rotations send one foot up
   and one down and renders look "unchanged"); (b) pose-bone rotations never reach the FBX
   bind pose, so the fix must be baked into the REST pose: apply the armature modifier to
   every mesh, `bpy.ops.pose.armature_apply`, rebind. Config: `foot_flat {axis:0, amount:0.75}`.
   Grounding, previews and all 144 clips inherit the planted stance automatically.

Also closed out: the ImportLog "Check clip reference frame … fajaw ROTATION differences
(4.056°)" errors on all MouthOpen_* variants are BENIGN — re-imported the shipped clip FBXs
and dumped the f-curves: parent and variants are byte-identical. Animaze ramp-sampling noise,
present since V50. Ignore forever (added to benign-noise list).

Lab discipline upgrade: judge hinge/pitch axes ONLY from side-profile renders (front views
fooled us on both the jaw and the feet), and remember EQ bone tails are auto-generated
garbage — only bone head positions mean anything.

## The one-line moral
Every "modernization" we offered Animaze broke the avatar; maximum EQ authenticity at every
layer (real tiles, real bone names, clips not morphs) was the winning move. Trust the log
files over the screenshots, the labs over intuition, and never ship what a diagnostic build
hasn't isolated.

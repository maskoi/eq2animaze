"""eq2animaze — one command, one avatar package.

Usage:
    python eq2animaze.py config_maskoi.json [version-tag]

Steps: validate assets -> Blender build (build_avatar.py, config-driven) ->
postprocess textures (color truth) -> report the import-ready folder.

Import protocol (see PIPELINE-PLAYBOOK.md): Animaze Editor -> Avatar3D ->
STANDARD -> Snap to ground -> Save -> Bundle. Expect + ignore the benign
dialogs (head bone, eye ranges, flat idle1).
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
HANDOFF = Path(__file__).resolve().parents[2]
POSTPROCESS = HANDOFF / "source" / "scripts" / "postprocess_textures.py"
BUILD = Path(__file__).resolve().parent / "build_avatar.py"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cfg_path = Path(sys.argv[1])
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).resolve().parent / cfg_path
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    tag = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%m%d-%H%M")
    out_name = f"{cfg['name']}-{tag}"
    out_dir = HANDOFF / "work" / f"IMPORT-ONLY-{out_name}"

    # ---- validate assets ----
    problems = []
    for key in ("base_glb", "plate_dir", "armor_tiles_dir"):
        if not (HANDOFF / cfg[key]).exists():
            problems.append(f"missing {key}: {cfg[key]}")
    for mod in cfg.get("greave_mods", []):
        if not (HANDOFF / cfg["plate_dir"] / mod).exists():
            problems.append(f"missing greave mod: {mod}")
    if problems:
        sys.exit("ASSET PROBLEMS:\n  " + "\n  ".join(problems))

    t0 = time.time()
    print(f"[eq2animaze] building {out_name} ...")

    env = os.environ.copy()
    env["EQ2ANIMAZE_CONFIG"] = str(cfg_path)
    env["EQ2ANIMAZE_OUTNAME"] = out_name
    r = subprocess.run([BLENDER, "--background", "--python", str(BUILD)],
                       env=env, capture_output=True, text=True, cwd=str(HANDOFF))
    if "Traceback" in (r.stdout + r.stderr) or not out_dir.exists():
        tail = "\n".join((r.stdout + "\n" + r.stderr).splitlines()[-25:])
        sys.exit(f"[eq2animaze] BUILD FAILED:\n{tail}")
    print(f"[eq2animaze] blender build ok ({time.time()-t0:.0f}s)")

    r = subprocess.run([sys.executable, str(POSTPROCESS), str(out_dir)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"[eq2animaze] POSTPROCESS FAILED:\n{r.stdout}\n{r.stderr}")
    composed = sum(1 for line in r.stdout.splitlines() if "composed" in line or "authentic" in line or "dyed" in line)
    print(f"[eq2animaze] postprocess ok ({composed} texture ops)")

    anims = len(list((out_dir / "Animations").glob("*.fbx")))
    print(f"""
[eq2animaze] DONE in {time.time()-t0:.0f}s
  package : {out_dir}
  clips   : {anims}
  import  : Animaze Editor -> Avatar3D -> STANDARD
            Snap to ground -> Save -> Bundle
  (ignore: head-bone dialog, eye-range zeros, flat-idle1 info)
""")


if __name__ == "__main__":
    main()

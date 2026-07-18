"""eq2animaze — one command, one avatar package.

Usage:
    python eq2animaze.py config_maskoi.json [version-tag] [--character manifest.json]

Steps: validate assets -> Blender build (build_avatar.py, config-driven) ->
postprocess textures (color truth) -> report the import-ready folder.

Import protocol (see PIPELINE-PLAYBOOK.md): Animaze Editor -> Avatar3D ->
STANDARD -> Snap to ground -> Save -> Bundle. Expect + ignore the benign
dialogs (head bone, eye ranges, flat idle1).
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
HANDOFF = Path(__file__).resolve().parents[2]
POSTPROCESS = HANDOFF / "source" / "scripts" / "postprocess_textures.py"
BUILD = Path(__file__).resolve().parent / "build_avatar.py"
from validate_package import ValidationError, validate_package
from character_manifest import CharacterManifestError, identity, load_character_manifest


def fail(message):
    sys.exit(f"[eq2animaze] {message}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    arguments = list(sys.argv[1:])
    cfg_path = Path(arguments.pop(0))
    character_path = None
    if "--character" in arguments:
        character_index = arguments.index("--character")
        if character_index + 1 >= len(arguments):
            fail("--character requires a manifest path")
        character_path = Path(arguments[character_index + 1]).expanduser().resolve()
        del arguments[character_index:character_index + 2]
    if len(arguments) > 1:
        fail("TOO MANY ARGUMENTS\n" + __doc__)
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).resolve().parent / cfg_path
    if not cfg_path.is_file():
        fail(f"CONFIG NOT FOUND: {cfg_path}")
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"CONFIG INVALID: {exc}")

    required_config = ("name", "base_glb", "plate_dir", "armor_tiles_dir", "quality")
    missing_config = [key for key in required_config if key not in cfg]
    if missing_config:
        fail("CONFIG MISSING: " + ", ".join(missing_config))

    character_manifest = None
    if character_path is not None:
        try:
            character_manifest = load_character_manifest(character_path)
        except CharacterManifestError as exc:
            fail(f"CHARACTER MANIFEST NOT READY: {exc}")
        print(f"[eq2animaze] character: {identity(character_manifest)}")

    tag = arguments[0] if arguments else datetime.now().strftime("%m%d-%H%M")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", tag):
        fail("TAG INVALID: use 1-64 letters, numbers, dots, underscores, or hyphens")
    out_name = f"{cfg['name']}-{tag}"
    out_dir = HANDOFF / "work" / f"IMPORT-ONLY-{out_name}"

    if not Path(BLENDER).is_file():
        fail(f"BLENDER NOT FOUND: {BLENDER}")
    if out_dir.exists():
        fail(f"OUTPUT ALREADY EXISTS: {out_dir}\nChoose a new tag; existing builds are immutable evidence.")

    # ---- validate assets ----
    problems = []
    for key in ("base_glb", "plate_dir", "armor_tiles_dir"):
        if not (HANDOFF / cfg[key]).exists():
            problems.append(f"missing {key}: {cfg[key]}")
    for mod in cfg.get("greave_mods", []):
        if not (HANDOFF / cfg["plate_dir"] / mod).exists():
            problems.append(f"missing greave mod: {mod}")
    if problems:
        fail("ASSET PROBLEMS:\n  " + "\n  ".join(problems))

    t0 = time.time()
    print(f"[eq2animaze] building {out_name} ...")

    env = os.environ.copy()
    env["EQ2ANIMAZE_CONFIG"] = str(cfg_path)
    env["EQ2ANIMAZE_OUTNAME"] = out_name
    if character_path is not None:
        env["EQ2ANIMAZE_CHARACTER_MANIFEST"] = str(character_path)
    r = subprocess.run([BLENDER, "--background", "--python", str(BUILD)],
                       env=env, capture_output=True, text=True, cwd=str(HANDOFF))
    combined_log = r.stdout + "\n" + r.stderr
    log_dir = HANDOFF / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    blender_log = log_dir / f"{out_name}-blender.log"
    blender_log.write_text(combined_log, encoding="utf-8", errors="replace")
    if r.returncode != 0 or "Traceback" in combined_log or not out_dir.exists():
        tail = "\n".join((r.stdout + "\n" + r.stderr).splitlines()[-25:])
        fail(f"BUILD FAILED (exit {r.returncode}; full log: {blender_log}):\n{tail}")
    print(f"[eq2animaze] blender build ok ({time.time()-t0:.0f}s)")

    r = subprocess.run([sys.executable, str(POSTPROCESS), str(out_dir)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"POSTPROCESS FAILED:\n{r.stdout}\n{r.stderr}")
    composed = sum(1 for line in r.stdout.splitlines() if "composed" in line or "authentic" in line or "dyed" in line)
    print(f"[eq2animaze] postprocess ok ({composed} texture ops)")

    if character_manifest is not None:
        provenance = out_dir / "character-manifest.json"
        provenance.write_text(
            json.dumps(character_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[eq2animaze] character provenance: {provenance.name}")

    try:
        report = validate_package(out_dir, out_name, cfg["quality"])
    except ValidationError as exc:
        fail(f"QUALITY GATE FAILED:\n  {exc}\nReport: {out_dir / 'build-report.json'}")
    anims = report["checks"]["animation_count"]
    print(f"""
[eq2animaze] DONE in {time.time()-t0:.0f}s
  package : {out_dir}
  clips   : {anims}
  quality : PASS ({out_dir / 'build-report.json'})
  log     : {blender_log}
  import  : Animaze Editor -> Avatar3D -> STANDARD
            Snap to ground -> Save -> Bundle
  (ignore: head-bone dialog, eye-range zeros, flat-idle1 info)
""")


if __name__ == "__main__":
    main()

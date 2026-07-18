"""Strict, dependency-free validation for an eq2animaze build folder."""

from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path


class ValidationError(RuntimeError):
    """Raised when a package fails one or more quality gates."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG dimensions without requiring Pillow in the build Python."""
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a valid PNG header")
    return struct.unpack(">II", header[16:24])


def _artifact(path: Path) -> dict:
    data = {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if path.suffix.lower() == ".png":
        data["dimensions"] = list(png_dimensions(path))
    return data


def validate_package(
    out_dir: Path,
    out_name: str,
    quality: dict,
    *,
    write_report: bool = True,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    main_fbx = out_dir / f"{out_name}.fbx"
    blend = out_dir / f"{out_name}.blend"
    animations_dir = out_dir / "Animations"
    textures_dir = out_dir / "Textures"

    minimums = quality.get("minimum_bytes", {})
    required_files = [
        (main_fbx, int(minimums.get("main_fbx", 100_000))),
        (blend, int(minimums.get("blend", 100_000))),
    ]
    for path, minimum in required_files:
        if not path.is_file():
            errors.append(f"missing required artifact: {path.name}")
        elif path.stat().st_size < minimum:
            errors.append(
                f"artifact is suspiciously small: {path.name} "
                f"({path.stat().st_size} bytes; minimum {minimum})"
            )

    animations = sorted(animations_dir.glob("*.fbx")) if animations_dir.is_dir() else []
    expected_count = quality.get("expected_animation_count")
    if expected_count is not None and len(animations) != int(expected_count):
        errors.append(
            f"animation count is {len(animations)}; expected exactly {expected_count}"
        )

    min_animation = int(minimums.get("animation_fbx", 100_000))
    too_small = [p.name for p in animations if p.stat().st_size < min_animation]
    if too_small:
        errors.append(
            f"{len(too_small)} animation FBX files are below {min_animation} bytes: "
            + ", ".join(too_small[:10])
        )

    animation_names = {p.stem for p in animations}
    required_animations = set(quality.get("required_animations", []))
    missing_animations = sorted(required_animations - animation_names)
    if missing_animations:
        errors.append("missing critical animations: " + ", ".join(missing_animations))

    texture_results = []
    for name, dimensions in quality.get("required_textures", {}).items():
        path = textures_dir / name
        if not path.is_file():
            errors.append(f"missing required texture: {name}")
            continue
        if path.stat().st_size < int(minimums.get("texture", 1_000)):
            errors.append(f"texture is suspiciously small: {name} ({path.stat().st_size} bytes)")
            continue
        try:
            actual_dimensions = png_dimensions(path)
        except ValueError as exc:
            errors.append(f"invalid texture {name}: {exc}")
            continue
        expected_dimensions = tuple(int(v) for v in dimensions)
        if actual_dimensions != expected_dimensions:
            errors.append(
                f"texture {name} is {actual_dimensions[0]}x{actual_dimensions[1]}; "
                f"expected {expected_dimensions[0]}x{expected_dimensions[1]}"
            )
        texture_results.append(_artifact(path))

    extra_textures = sorted(
        p.name
        for p in textures_dir.glob("*.png")
        if p.name not in quality.get("required_textures", {})
    ) if textures_dir.is_dir() else []
    if extra_textures:
        warnings.append("unrecognized textures present: " + ", ".join(extra_textures))

    report = {
        "schema": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "package": out_name,
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "animation_count": len(animations),
            "required_animation_count": len(required_animations),
            "texture_count": len(list(textures_dir.glob("*.png"))) if textures_dir.is_dir() else 0,
        },
        "artifacts": {
            "main": [_artifact(p) for p, _ in required_files if p.is_file()],
            "textures": texture_results,
            "animations": [_artifact(p) for p in animations],
        },
    }

    if write_report:
        report_path = out_dir / "build-report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if errors:
        raise ValidationError("\n  ".join(errors))
    return report

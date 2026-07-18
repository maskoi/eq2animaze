"""Validation and provenance support for EQ character-capture manifests."""

from __future__ import annotations

import json
from pathlib import Path


class CharacterManifestError(ValueError):
    pass


def load_character_manifest(path: Path, *, require_ready: bool = True) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CharacterManifestError(f"cannot read character manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CharacterManifestError(f"character manifest is invalid JSON: {exc}") from exc

    if manifest.get("schema") != 1:
        raise CharacterManifestError("character manifest schema must be 1")

    character = manifest.get("character")
    if not isinstance(character, dict) or not character.get("name") or not character.get("server"):
        raise CharacterManifestError("character manifest requires character.name and character.server")

    if not isinstance(manifest.get("equipment"), list):
        raise CharacterManifestError("character manifest equipment must be an array")
    if not isinstance(manifest.get("appearance"), dict):
        raise CharacterManifestError("character manifest appearance must be an object")

    generator = manifest.get("generator")
    if not isinstance(generator, dict) or not isinstance(generator.get("ready"), bool):
        raise CharacterManifestError("character manifest requires generator.ready")

    if require_ready and not generator["ready"]:
        missing = generator.get("missing_fields", [])
        detail = ", ".join(str(value) for value in missing) or "unspecified appearance data"
        raise CharacterManifestError(
            "character manifest is captured but not generator-ready; missing: " + detail
        )
    return manifest


def identity(manifest: dict) -> str:
    character = manifest["character"]
    return f"{character['name']}-{character['server']}"


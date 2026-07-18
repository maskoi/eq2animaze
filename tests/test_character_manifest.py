import json
import sys
import tempfile
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1] / "source" / "pipeline"
sys.path.insert(0, str(PIPELINE))

from character_manifest import CharacterManifestError, identity, load_character_manifest


class CharacterManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "character.json"
        self.manifest = {
            "schema": 1,
            "character": {"name": "Ironscales", "server": "tunare"},
            "equipment": [],
            "appearance": {"race_name": "Iksar", "gender": "male"},
            "generator": {"ready": True, "missing_fields": []},
        }

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_ready_manifest_loads(self):
        self.write()
        loaded = load_character_manifest(self.path)
        self.assertEqual("Ironscales-tunare", identity(loaded))

    def test_incomplete_manifest_names_missing_fields(self):
        self.manifest["generator"] = {
            "ready": False,
            "missing_fields": ["face", "equipment_tints"],
        }
        self.write()
        with self.assertRaisesRegex(CharacterManifestError, "face, equipment_tints"):
            load_character_manifest(self.path)

    def test_capture_stage_can_load_incomplete_manifest(self):
        self.manifest["generator"]["ready"] = False
        self.write()
        loaded = load_character_manifest(self.path, require_ready=False)
        self.assertFalse(loaded["generator"]["ready"])

    def test_wrong_schema_fails(self):
        self.manifest["schema"] = 2
        self.write()
        with self.assertRaisesRegex(CharacterManifestError, "schema must be 1"):
            load_character_manifest(self.path)


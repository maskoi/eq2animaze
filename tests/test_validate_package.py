import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1] / "source" / "pipeline"
sys.path.insert(0, str(PIPELINE))

from validate_package import ValidationError, validate_package


def png_bytes(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\x00" + b"\x00\x00\x00\xff" * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


class PackageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "Animations").mkdir()
        (self.root / "Textures").mkdir()
        (self.root / "Test.fbx").write_bytes(b"f" * 20)
        (self.root / "Test.blend").write_bytes(b"b" * 20)
        (self.root / "Animations" / "idle1.fbx").write_bytes(b"a" * 20)
        (self.root / "Textures" / "atlas.png").write_bytes(png_bytes(2, 1))
        self.quality = {
            "expected_animation_count": 1,
            "minimum_bytes": {
                "main_fbx": 10,
                "blend": 10,
                "animation_fbx": 10,
                "texture": 10,
            },
            "required_animations": ["idle1"],
            "required_textures": {"atlas.png": [2, 1]},
        }

    def tearDown(self):
        self.temp.cleanup()

    def validate(self):
        return validate_package(self.root, "Test", self.quality, write_report=False)

    def test_known_good_package_passes(self):
        self.assertEqual("pass", self.validate()["status"])

    def test_missing_main_fbx_fails(self):
        (self.root / "Test.fbx").unlink()
        with self.assertRaisesRegex(ValidationError, "missing required artifact"):
            self.validate()

    def test_wrong_animation_count_fails(self):
        (self.root / "Animations" / "extra.fbx").write_bytes(b"a" * 20)
        with self.assertRaisesRegex(ValidationError, "animation count is 2"):
            self.validate()

    def test_missing_critical_animation_fails(self):
        self.quality["required_animations"] = ["MouthOpen"]
        with self.assertRaisesRegex(ValidationError, "missing critical animations"):
            self.validate()

    def test_corrupt_texture_fails(self):
        (self.root / "Textures" / "atlas.png").write_bytes(b"not a png at all")
        with self.assertRaisesRegex(ValidationError, "invalid texture"):
            self.validate()

    def test_wrong_texture_dimensions_fail(self):
        self.quality["required_textures"]["atlas.png"] = [4, 4]
        with self.assertRaisesRegex(ValidationError, "expected 4x4"):
            self.validate()


if __name__ == "__main__":
    unittest.main()


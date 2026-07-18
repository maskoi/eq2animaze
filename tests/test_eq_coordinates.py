import json
import sys
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1] / "source" / "pipeline"
sys.path.insert(0, str(PIPELINE))

from eq_coordinates import (
    EQ_LOCATION_ORDER,
    EQ_TO_LANTERN_BONE,
    EQ_TO_LANTERN_MESH,
    apply,
    determinant,
    lantern_mesh_to_bone_matrix,
)


class EverQuestCoordinateContractTests(unittest.TestCase):
    def test_eq_location_order_is_y_x_z(self):
        self.assertEqual(("y", "x", "z"), EQ_LOCATION_ORDER)

    def test_lantern_bone_mapping_matches_source(self):
        self.assertEqual((2.0, 5.0, -3.0), apply(EQ_TO_LANTERN_BONE, (2, 3, 5)))

    def test_lantern_mesh_mapping_matches_source(self):
        self.assertEqual((-2.0, 5.0, 3.0), apply(EQ_TO_LANTERN_MESH, (2, 3, 5)))

    def test_complete_lantern_mappings_preserve_handedness(self):
        self.assertEqual(1.0, determinant(EQ_TO_LANTERN_BONE))
        self.assertEqual(1.0, determinant(EQ_TO_LANTERN_MESH))

    def test_relative_orientation_is_180_degree_y_rotation(self):
        relative = lantern_mesh_to_bone_matrix()
        self.assertEqual(
            ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)),
            relative,
        )
        self.assertEqual(1.0, determinant(relative))

    def test_maskoi_config_declares_the_same_contract(self):
        config_path = PIPELINE / "config_maskoi.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        contract = config["coordinate_contract"]
        self.assertEqual(1, contract["revision"])
        self.assertEqual(list(EQ_LOCATION_ORDER), contract["eq_location_order"])
        self.assertEqual(["x", "z", "-y"], contract["lantern_bone_vector"])
        self.assertEqual(["-x", "z", "y"], contract["lantern_mesh_vector"])
        self.assertTrue(contract["animation_signs_are_per_rig"])


if __name__ == "__main__":
    unittest.main()

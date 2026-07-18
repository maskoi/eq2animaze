"""Coordinate contracts for EverQuest -> LanternExtractor -> Blender."""

from __future__ import annotations

from typing import Iterable


Matrix3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]
Vector3 = tuple[float, float, float]


# EQ /loc and MQ APIs present locations as Y, X, Z.
EQ_LOCATION_ORDER = ("y", "x", "z")

# Lantern ApplyBoneTransformation maps translation and quaternion vector parts
# from (x, y, z) to (x, z, -y).
EQ_TO_LANTERN_BONE: Matrix3 = (
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, -1.0, 0.0),
)

# Lantern mesh vertices swap Y/Z and the mesh node receives an X reflection.
EQ_TO_LANTERN_MESH: Matrix3 = (
    (-1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
)


def apply(matrix: Matrix3, vector: Iterable[float]) -> Vector3:
    x, y, z = (float(value) for value in vector)
    return tuple(
        row[0] * x + row[1] * y + row[2] * z
        for row in matrix
    )  # type: ignore[return-value]


def determinant(matrix: Matrix3) -> float:
    a, b, c = matrix
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def transpose(matrix: Matrix3) -> Matrix3:
    return tuple(
        tuple(matrix[row][column] for row in range(3))
        for column in range(3)
    )  # type: ignore[return-value]


def multiply(left: Matrix3, right: Matrix3) -> Matrix3:
    return tuple(
        tuple(
            sum(left[row][k] * right[k][column] for k in range(3))
            for column in range(3)
        )
        for row in range(3)
    )  # type: ignore[return-value]


def lantern_mesh_to_bone_matrix() -> Matrix3:
    """Return the relative orientation from Lantern mesh to bone space."""
    return multiply(EQ_TO_LANTERN_BONE, transpose(EQ_TO_LANTERN_MESH))


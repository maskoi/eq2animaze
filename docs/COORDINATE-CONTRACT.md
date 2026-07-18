# EverQuest coordinate contract

This document is the source of truth for axis-sensitive pipeline work.

## Confirmed in the local MQ2 source

- EverQuest `/loc` displays **Y, X, Z**.
- MQ2 facing calculations use `atan2(delta-X, delta-Y)` rather than the
  conventional `atan2(delta-Y, delta-X)`.
- Existing KissAssist movement code stores and passes camp locations as Y, X.

This is an engine convention, not an Animaze symptom.

## Confirmed in LanternExtractor

| Data | EQ input | Lantern output | Determinant |
|---|---|---|---:|
| Bone translation and quaternion vector | `(x, y, z)` | `(x, z, -y)` | `+1` |
| Mesh vertex after node X reflection | `(x, y, z)` | `(-x, z, y)` | `+1` |

The complete conversions preserve handedness. Their relative orientation is
`(-x, y, -z)`, a 180-degree rotation around Y. Do not describe the finished
Lantern output as one unresolved handedness flip.

## Pipeline rules

1. Never add an unrecorded global axis swap, mirror, or 180-degree correction.
2. Preserve the Lantern scene hierarchy when importing the GLB.
3. Treat facial and body animation directions as per-rig configuration.
4. If Blender and Animaze disagree, inspect the exported FBX curve and bone
   local basis before changing geometry or the rest pose.
5. A sign proven in Animaze wins, but record the package version and result.
6. New races require an axis lab; similar bone names do not prove similar
   local frames.

## Diagnostic interpretation

- Wrong facing or camera side: inspect the root/node orientation.
- Entire body mirrored: inspect the global conversion exactly once.
- One joint rotates backward: verify that joint's configured sign; do not
  mirror the avatar.
- Mesh correct but animation deforms catastrophically: verify bind matrices,
  parent hierarchy, and whether a conversion was applied twice.
- Texture and color errors are unrelated to coordinate conversion.

The executable contract is `source/pipeline/eq_coordinates.py`, with regression
coverage in `tests/test_eq_coordinates.py`.


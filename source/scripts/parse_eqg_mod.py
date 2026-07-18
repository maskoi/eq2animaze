"""Read EverQuest EQG .mod meshes and export Blender-friendly OBJ files.

The binary layout follows Quail v1.6.0's MIT-licensed raw/mod_read.go parser.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read(self, fmt: str):
        size = struct.calcsize("<" + fmt)
        if self.pos + size > len(self.data):
            raise EOFError(f"need {size} bytes at {self.pos}, file has {len(self.data)}")
        value = struct.unpack_from("<" + fmt, self.data, self.pos)
        self.pos += size
        return value[0] if len(value) == 1 else value

    def bytes(self, count: int) -> bytes:
        value = self.data[self.pos:self.pos + count]
        if len(value) != count:
            raise EOFError(f"need {count} bytes at {self.pos}")
        self.pos += count
        return value


def string_table(data: bytes) -> dict[int, str]:
    names: dict[int, str] = {}
    start = 0
    for index, byte in enumerate(data):
        if byte == 0:
            names[start] = data[start:index].decode("utf-8", errors="replace")
            start = index + 1
    return names


def name_at(names: dict[int, str], offset: int) -> str:
    return names.get(abs(offset), f"!UNK({abs(offset)})")


@dataclass
class ModMesh:
    path: Path
    version: int
    materials: list[dict]
    vertices: list[dict]
    faces: list[dict]
    bones: list[dict]

    def bounds(self):
        xyz = [v["position"] for v in self.vertices]
        return tuple(min(v[i] for v in xyz) for i in range(3)), tuple(max(v[i] for v in xyz) for i in range(3))


def read_mod(path: Path) -> ModMesh:
    reader = Reader(path.read_bytes())
    header = reader.bytes(4)
    version = reader.read("I")
    if header != b"EQGM":
        raise ValueError(f"{path.name}: expected EQGM, got {header!r}")

    name_length, material_count, vertex_count, face_count, bone_count = reader.read("IIIII")
    names = string_table(reader.bytes(name_length))

    materials = []
    for _ in range(material_count):
        material_id, material_name, shader_name = reader.read("iii")
        params = []
        for _ in range(reader.read("I")):
            param_name = name_at(names, reader.read("i"))
            param_type = reader.read("I")
            if param_type == 0:
                value = reader.read("f")
            else:
                raw_value = reader.read("i")
                value = name_at(names, raw_value) if param_type == 2 else raw_value
            params.append({"name": param_name, "type": param_type, "value": value})
        materials.append({
            "id": material_id,
            "name": name_at(names, material_name),
            "shader": name_at(names, shader_name),
            "params": params,
        })

    vertices = []
    for _ in range(vertex_count):
        position = reader.read("fff")
        normal = reader.read("fff")
        tint = (128, 128, 128, 255) if version <= 2 else reader.read("BBBB")
        uv = reader.read("ff")
        uv2 = (0.0, 0.0) if version <= 2 else reader.read("ff")
        vertices.append({"position": position, "normal": normal, "tint": tint, "uv": uv, "uv2": uv2, "weights": []})

    faces = []
    for _ in range(face_count):
        indices = reader.read("III")
        material_id = reader.read("i")
        flags = reader.read("I")
        faces.append({"indices": indices, "material": material_id, "flags": flags})

    bones = []
    for _ in range(bone_count):
        bones.append({
            "name": name_at(names, reader.read("i")),
            "next": reader.read("i"),
            "children_count": reader.read("I"),
            "child_index": reader.read("i"),
            "pivot": reader.read("fff"),
            "quaternion": reader.read("ffff"),
            "scale": reader.read("fff"),
        })

    for vertex in vertices:
        count = reader.read("i")
        weights = []
        for slot in range(4):
            bone_index = reader.read("i")
            value = reader.read("f")
            if slot < count:
                weights.append({"bone": bone_index, "value": value})
        vertex["weights"] = weights

    # Live armor files end immediately after the weight table; some Quail
    # revisions also accept an optional trailing zero uint32.
    excess = reader.read("I") if reader.pos < len(reader.data) else 0
    if excess != 0 or reader.pos != len(reader.data):
        raise ValueError(f"{path.name}: excess={excess}, consumed={reader.pos}, size={len(reader.data)}")
    return ModMesh(path, version, materials, vertices, faces, bones)


def export_obj(mesh: ModMesh, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Converted from {mesh.path.name}", f"o {mesh.path.stem}"]
    for vertex in mesh.vertices:
        lines.append("v " + " ".join(f"{x:.8f}" for x in vertex["position"]))
    for vertex in mesh.vertices:
        lines.append(f"vt {vertex['uv'][0]:.8f} {1.0 - vertex['uv'][1]:.8f}")
    for vertex in mesh.vertices:
        lines.append("vn " + " ".join(f"{x:.8f}" for x in vertex["normal"]))
    current_material = None
    for face in mesh.faces:
        material_id = face["material"]
        if material_id != current_material:
            material_name = mesh.materials[material_id]["name"] if 0 <= material_id < len(mesh.materials) else "unassigned"
            lines.append(f"usemtl {material_name}")
            current_material = material_id
        a, b, c = (index + 1 for index in face["indices"])
        lines.append(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output.with_suffix(".weights.json").write_text(json.dumps({
        "source": str(mesh.path),
        "materials": mesh.materials,
        "bones": mesh.bones,
        "weights": [vertex["weights"] for vertex in mesh.vertices],
    }, indent=2), encoding="utf-8")


def scan(directory: Path, output_csv: Path, export_dir: Path | None):
    rows = []
    for path in sorted(directory.glob("*.mod")):
        mesh = read_mod(path)
        minimum, maximum = mesh.bounds()
        rows.append({
            "file": path.name,
            "version": mesh.version,
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "materials": len(mesh.materials),
            "bones": len(mesh.bones),
            "min_x": minimum[0], "min_y": minimum[1], "min_z": minimum[2],
            "max_x": maximum[0], "max_y": maximum[1], "max_z": maximum[2],
            "bone_names": ";".join(bone["name"] for bone in mesh.bones),
            "material_names": ";".join(material["name"] for material in mesh.materials),
        })
        if export_dir:
            export_obj(mesh, export_dir / f"{path.stem}.obj")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["file"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Parsed {len(rows)} files -> {output_csv}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--csv", type=Path, default=Path("mod-summary.csv"))
    parser.add_argument("--export-dir", type=Path)
    args = parser.parse_args()
    scan(args.directory, args.csv, args.export_dir)


if __name__ == "__main__":
    main()

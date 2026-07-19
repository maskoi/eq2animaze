import bpy
import math
import sys
import json
import os
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

HANDOFF_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = HANDOFF_ROOT / "source" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
from parse_eqg_mod import read_mod

# ---- config-driven (eq2animaze) ----
_cfg_path = os.environ.get("EQ2ANIMAZE_CONFIG")
_out_name = os.environ.get("EQ2ANIMAZE_OUTNAME")
with open(_cfg_path, encoding="utf-8") as _f:
    CFG = json.load(_f)
AX = CFG["axes"]

BASE_GLB = HANDOFF_ROOT / CFG["base_glb"]
PLATE_DIR = HANDOFF_ROOT / CFG["plate_dir"]
HELM_GLB = Path(r"C:/Users/Raphael/Documents/Codex/2026-07-14/LanternExtractor-0.1.7.win-x64/Exports/global4/Characters/ikm_03.glb")
OUT_DIR = HANDOFF_ROOT / "work" / ("IMPORT-ONLY-" + _out_name)
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_BLEND = OUT_DIR / (_out_name + ".blend")
OUT_FBX = OUT_DIR / (_out_name + ".fbx")
OUT_PREVIEW = OUT_DIR / (_out_name + "-preview.png")
OUT_PORTRAIT = OUT_DIR / (_out_name + "-portrait.png")
TEXTURE_DIR = OUT_DIR / "Textures"
TEXTURE_DIR.mkdir(parents=True, exist_ok=True)
ANIM_DIR = OUT_DIR / "Animations"
ANIM_DIR.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(BASE_GLB))
armature = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
body = max((obj for obj in bpy.context.scene.objects if obj.type == 'MESH'), key=lambda obj: len(obj.data.vertices))
armature.name = "Maskoi_Rig"
body.name = "Maskoi_Body"

# The source GLB carries a stray unmaterialed Icosphere; it exports as a black
# blob in Animaze, so remove it before anything else.
for junk in [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("Icosphere")]:
    bpy.data.objects.remove(junk, do_unlink=True)

# Animaze's retargeter cannot identify EQ bone names ("no headbone" on every
# import). Rename the tracking-critical bones to standard humanoid names it
# auto-maps. All animation clips are exported from this same armature, so the
# names stay consistent across the whole package.
BONE_RENAMES = {}  # V43: pure EQ names; Animaze look-at mangles this rig's bones
for old_name, new_name in BONE_RENAMES.items():
    bone = armature.data.bones.get(old_name)
    if bone:
        bone.name = new_name
# Blender usually syncs vertex-group names on bone rename; enforce it.
for mesh_obj in [o for o in bpy.data.objects if o.type == 'MESH']:
    for old_name, new_name in BONE_RENAMES.items():
        vg = mesh_obj.vertex_groups.get(old_name)
        if vg and not mesh_obj.vertex_groups.get(new_name):
            vg.name = new_name
print("BONE RENAME check:", [b.name for b in armature.data.bones if b.name in BONE_RENAMES.values()])

# Animaze rejects negative UV coordinates even though EverQuest uses ordinary
# texture wrapping. Folding them into the equivalent 0..1 range preserves the
# appearance and removes the mesh-import warnings.
for uv_layer in body.data.uv_layers:
    for loop in uv_layer.data:
        loop.uv.x %= 1.0
        loop.uv.y %= 1.0


def material_principled(name, color, metallic=0.0, roughness=0.5, emission=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emission:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = (*emission, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 2.4
    return mat


emerald = material_principled("Maskoi Emerald Dye", (0.003, 0.20, 0.055), 0.52, 0.32)
emerald_dark = material_principled("Maskoi Emerald Shadow", (0.002, 0.055, 0.014), 0.42, 0.38)
gem = material_principled("Maskoi Forehead Gem", (0.10, 0.01, 0.65), 0.25, 0.18, (0.12, 0.01, 0.75))
claw = material_principled("Maskoi Claw Metal", (0.55, 0.62, 0.68), 0.55, 0.28)


def direct_image_link(material, image):
    """Use the simple Image -> Base Color graph supported by Animaze's FBX SDK."""
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
    for link in list(bsdf.inputs['Base Color'].links):
        links.remove(link)
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = image
    links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Base Color'].default_value = (1, 1, 1, 1)


def solid_texture(material, color):
    image = bpy.data.images.new(material.name + " Texture", width=8, height=8, alpha=True)
    image.generated_color = (*color, 1.0)
    image.pixels = list((*color, 1.0)) * 64
    direct_image_link(material, image)


def tinted_copy(source, name, tint, factor):
    source.update()
    pixels = list(source.pixels[:])
    for index in range(0, len(pixels), 4):
        pixels[index] = pixels[index] * (1.0 - factor) + tint[0] * factor
        pixels[index + 1] = pixels[index + 1] * (1.0 - factor) + tint[1] * factor
        pixels[index + 2] = pixels[index + 2] * (1.0 - factor) + tint[2] * factor
    image = bpy.data.images.new(name, width=source.size[0], height=source.size[1], alpha=True)
    image.pixels = pixels
    image.update()
    return image


def multiplied_copy(source, name, mult):
    """EQ-style armor tint: multiply the texture so marble detail survives."""
    source.update()
    pixels = list(source.pixels[:])
    for index in range(0, len(pixels), 4):
        pixels[index] = min(1.0, pixels[index] * mult[0])
        pixels[index + 1] = min(1.0, pixels[index + 1] * mult[1])
        pixels[index + 2] = min(1.0, pixels[index + 2] * mult[2])
    image = bpy.data.images.new(name, width=source.size[0], height=source.size[1], alpha=True)
    image.pixels = pixels
    image.update()
    return image


def fill_masked(image):
    """Animaze ignores Blender's alpha-mask node chain, rendering masked texels
    as solid black. Fill them with the mean opaque color so the plates read as
    solid fins either way (the in-game reference fins look solid)."""
    image.update()
    pixels = list(image.pixels[:])
    total = [0.0, 0.0, 0.0]
    count = 0
    for index in range(0, len(pixels), 4):
        if pixels[index + 3] >= 0.5:
            total[0] += pixels[index]; total[1] += pixels[index + 1]; total[2] += pixels[index + 2]
            count += 1
    mean = [c / max(count, 1) for c in total]
    for index in range(0, len(pixels), 4):
        if pixels[index + 3] < 0.5:
            pixels[index], pixels[index + 1], pixels[index + 2] = mean
            pixels[index + 3] = 1.0
    image.pixels = pixels
    image.update()


solid_texture(emerald, (0.01, 0.32, 0.07))
solid_texture(emerald_dark, (0.005, 0.09, 0.02))
solid_texture(gem, (0.18, 0.02, 0.85))
solid_texture(claw, (0.55, 0.62, 0.68))


def make_velious_plate_material():
    material = bpy.data.materials.new("Maskoi Genuine Velious Plate")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
    source = bpy.data.images.load(str(PLATE_DIR / 'velious_plate_ikm_c.dds'), check_existing=True)
    # Linear-space multipliers solved analytically so the sRGB-encoded export
    # averages (12,134,100) -- the armor teal sampled from the in-game
    # Ironscales reference screenshot.
    dyed = multiplied_copy(source, "Maskoi Velious Plate Emerald", (0.0186, 1.2992, 0.8937))
    direct_image_link(material, dyed)
    bsdf.inputs['Metallic'].default_value = 0.38
    bsdf.inputs['Roughness'].default_value = 0.42
    return material


velious_plate = make_velious_plate_material()
velious_plate_image = next(
    node.image for node in velious_plate.node_tree.nodes
    if node.type == 'TEX_IMAGE' and node.image
)


def tint_existing_material(mat, tint=(0.01, 0.72, 0.28, 1.0)):
    if not mat or not mat.use_nodes:
        return
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return
    base = bsdf.inputs['Base Color']
    source_node = base.links[0].from_node if base.links and base.links[0].from_node.type == 'TEX_IMAGE' else None
    if source_node and source_node.image:
        direct_image_link(mat, source_node.image)
    else:
        solid_texture(mat, tint[:3])
    bsdf.inputs['Metallic'].default_value = 0.18
    bsdf.inputs['Roughness'].default_value = 0.42


# The armored body look: EQ swaps each body-region texture tile for the
# armor set's tile. Cohort's Legionnaire renders as plate (set 04) with the
# item's teal tint (applied later in postprocess_textures.py). Swap each
# naked-set tile (ikmXXskNN) for its set-04 counterpart in place, keeping the
# proven material graphs untouched.
import re as _re
SET04_DIR = HANDOFF_ROOT / CFG["armor_tiles_dir"]
ARMOR_PARTS = tuple(CFG['armor_parts'])
for mat in body.data.materials:
    if not mat or not mat.use_nodes:
        continue
    m = _re.match(r"(?:d|tm)_" + CFG["race_token"] + r"(\w\w)sk(\d\d)$", mat.name)
    if not m or m.group(1) not in ARMOR_PARTS:
        continue
    tile = SET04_DIR / f"{CFG['race_token']}{m.group(1)}{CFG['armor_set']}{m.group(2)}.png"
    if not tile.exists():
        continue
    armor_img = bpy.data.images.load(str(tile), check_existing=True)
    armor_img.name = tile.stem
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            node.image = armor_img

# Pose snapshot support: captured after the animation section restores the
# source action at frame 1 (the canonical export stance).
POSE_SNAPSHOT = {}

def restore_pose():
    for pb in armature.pose.bones:
        if pb.name in POSE_SNAPSHOT:
            pb.matrix_basis = POSE_SNAPSHOT[pb.name].copy()
    bpy.context.view_layer.update()

bone_lookup = {bone.name.lower(): bone.name for bone in armature.data.bones}


def compensate_current_pose(obj):
    """Pre-transform authored armor so the active EQ pose lands at its source coordinates."""
    for vertex in obj.data.vertices:
        desired = vertex.co.copy()
        deform = Matrix(((0.0, 0.0, 0.0, 0.0),) * 4)
        total = 0.0
        for membership in vertex.groups:
            group_name = obj.vertex_groups[membership.group].name
            pose_bone = armature.pose.bones.get(group_name)
            rest_bone = armature.data.bones.get(group_name)
            if not pose_bone or not rest_bone or membership.weight <= 0:
                continue
            transform = pose_bone.matrix @ rest_bone.matrix_local.inverted_safe()
            for row in range(4):
                for column in range(4):
                    deform[row][column] += transform[row][column] * membership.weight
            total += membership.weight
        if total < 1.0:
            identity = Matrix.Identity(4)
            for row in range(4):
                for column in range(4):
                    deform[row][column] += identity[row][column] * (1.0 - total)
        vertex.co = deform.inverted_safe() @ desired


def import_mod_mesh(path, name):
    mod = read_mod(path)
    verts = [vertex['position'] for vertex in mod.vertices]
    faces = [face['indices'] for face in mod.faces]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(velious_plate)
    mesh.materials.append(velious_plate)
    for polygon, face in zip(mesh.polygons, mod.faces):
        polygon.material_index = max(0, min(face['material'], 1))

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            u, v = mod.vertices[vertex_index]['uv']
            uv_layer.data[loop_index].uv = (u, 1.0 - v)

    # EQG armor bone weights use a different bind convention. Transfer the
    # nearest weights from the already-correct Iksar body instead; this keeps
    # the raw armor perfectly aligned and makes it follow the same live rig.
    for group in body.vertex_groups:
        obj.vertex_groups.new(name=group.name)
    # The armor pieces are authored in POSED world space, but the body's raw
    # vertex coords are BIND space (where the head sits at leg height!).
    # Matching in bind space silently weighted the greaves to HEAD and FACE
    # bones. Match against the evaluated (posed) body instead.
    eval_deps = bpy.context.evaluated_depsgraph_get()
    eval_body = body.evaluated_get(eval_deps)
    eval_mesh = eval_body.to_mesh()
    kd = KDTree(len(eval_mesh.vertices))
    for vertex in eval_mesh.vertices:
        kd.insert(body.matrix_world @ vertex.co, vertex.index)
    kd.balance()
    eval_body.to_mesh_clear()
    for vertex in obj.data.vertices:
        _, nearest_index, _ = kd.find(vertex.co)
        source = body.data.vertices[nearest_index]
        for membership in source.groups:
            source_group = body.vertex_groups[membership.group]
            obj.vertex_groups[source_group.name].add([vertex.index], membership.weight, 'REPLACE')
    modifier = obj.modifiers.new("Maskoi Armature", 'ARMATURE')
    modifier.object = armature
    obj.parent = armature
    compensate_current_pose(obj)
    return obj


# Genuine Velious Iksar plate greaves and clawed boots, in their verified raw
# alignment. The nearest-body weight transfer above avoids the bad bind pose.
for _i, _mod in enumerate(CFG.get("greave_mods", [])):
    import_mod_mesh(PLATE_DIR / _mod, f"Armor_Piece_{_i}")


def bone_parent(obj, bone_name):
    # Geometry is authored in the same global bind coordinates as the body.
    # Rigid skinning preserves that alignment and follows the selected bone in
    # Animaze without the offset introduced by Blender's BONE parent mode.
    group = obj.vertex_groups.new(name=bone_lookup.get(bone_name.lower(), bone_name))
    group.add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
    modifier = obj.modifiers.new("Maskoi Armature", 'ARMATURE')
    modifier.object = armature
    obj.parent = armature
    compensate_current_pose(obj)


def beveled_cube(name, location, scale, material, bone, bevel=0.16, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = obj.modifiers.new("Forged bevel", 'BEVEL')
    modifier.width = bevel
    modifier.segments = 2
    obj.data.materials.append(material)
    bone_parent(obj, bone)
    return obj


def ico(name, location, scale, material, bone, subdivisions=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    obj.data.materials.append(material)
    bone_parent(obj, bone)
    return obj


def cone(name, location, radius1, radius2, depth, rotation, material, bone):
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=radius1, radius2=radius2, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bevel = obj.modifiers.new("Forged bevel", 'BEVEL')
    bevel.width = 0.07
    bevel.segments = 2
    bone_parent(obj, bone)
    return obj


def poly_object(name, vertices, faces, material, bone):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new("Forged edges", 'BEVEL')
    bevel.width = 0.035
    bevel.segments = 1
    bone_parent(obj, bone)
    return obj


# The real Iksar shoulder spikes already provide the correct silhouette. The
# body armor texture slots carry the green dye without adding blocky guards.

# V17: helmet omitted by request -- the authentic bare Iksar head ships as-is.
# (The IKMHE03 transplant lives in build_maskoi_V16_cleanshapes.py if wanted later.)

def group_weight(vertex, group_name):
    group = body.vertex_groups.get(group_name)
    if group is None:
        return 0.0
    for membership in vertex.groups:
        if membership.group == group.index:
            return membership.weight
    return 0.0


# The shape-move table describes deltas in POSED-WORLD directions, but the
# vertices live in BIND space (where this rig's head is inverted). Applying
# world deltas raw crumples/flips face polys the moment a blendshape fires
# (= the black flickering face in the app). Rotate each delta through the
# vertex's bind->pose transform so morphs move the right way in-game.
_vertex_deform_inv = {}
for _v in body.data.vertices:
    deform = Matrix(((0.0, 0.0, 0.0, 0.0),) * 4)
    total = 0.0
    for _m in _v.groups:
        gname = body.vertex_groups[_m.group].name
        pb = armature.pose.bones.get(gname)
        rb = armature.data.bones.get(gname)
        if not pb or not rb or _m.weight <= 0:
            continue
        t = pb.matrix @ rb.matrix_local.inverted_safe()
        for r in range(4):
            for c in range(4):
                deform[r][c] += t[r][c] * _m.weight
        total += _m.weight
    if total < 1.0:
        for r in range(4):
            deform[r][r] += (1.0 - total)
    _vertex_deform_inv[_v.index] = deform.to_3x3().inverted_safe()


def add_shape(name, moves):
    key = body.shape_key_add(name=name)
    for vertex in body.data.vertices:
        delta = Vector((0, 0, 0))
        for group_name, movement in moves:
            delta += Vector(movement) * group_weight(vertex, group_name)
        if delta.length_squared > 0.0:
            delta = _vertex_deform_inv[vertex.index] @ delta
        key.data[vertex.index].co = vertex.co + delta
    return key


# V45 DIAGNOSTIC: NO blendshapes at all. If the app face renders clean,
# the morph data is the culprit; if still black, geometry/atlas-side.


# Required Animaze skeletal animation stacks. These small, clean clips drive
# head/body look motion, natural idle, eyes and hands. Optional ear/tongue clips
# use the nearest available Iksar bones so the importer has a complete tree.
source_action = armature.animation_data.action if armature.animation_data else None
animaze_actions = []

# Law-5 canonical reference (D7): capture every bone's rest rotation ONCE, in XYZ,
# BEFORE any clip is built. All clip builders below take their frame-1 base from
# this instead of the LIVE bone rotation -- which a prior clip silently poisons
# (the active action re-evaluates e.g. fajaw to its open value, so the next clip's
# "rest" base is 0.35 rad off -> Animaze's "fajaw ROTATION differences (20deg)").
for _pb in armature.pose.bones:
    _pb.rotation_mode = 'XYZ'
REST_REF = {_pb.name: _pb.rotation_euler.copy() for _pb in armature.pose.bones}


def make_rotation_action(name, bone_name, axis, amount):
    bone = armature.pose.bones.get(bone_lookup.get(bone_name.lower(), bone_name))
    if not bone:
        return
    action = bpy.data.actions.new(name)
    animaze_actions.append(action)
    armature.animation_data_create()
    armature.animation_data.action = action
    bone.rotation_mode = 'XYZ'
    base = REST_REF.get(bone.name, bone.rotation_euler.copy())  # D7: canonical rest
    for frame, factor in ((1, 0.0), (8, 1.0), (16, 0.0)):
        bone.rotation_euler = base.copy()
        bone.rotation_euler[axis] += amount * factor
        bone.keyframe_insert('rotation_euler', frame=frame, group=bone.name)
    bone.rotation_euler = base


def make_location_action(name, bone_name, axis, amount):
    bone = armature.pose.bones.get(bone_lookup.get(bone_name.lower(), bone_name))
    if not bone:
        return
    action = bpy.data.actions.new(name)
    animaze_actions.append(action)
    armature.animation_data_create()
    armature.animation_data.action = action
    base = bone.location.copy()
    for frame, factor in ((1, 0.0), (8, 1.0), (16, 0.0)):
        bone.location = base.copy()
        bone.location[axis] += amount * factor
        bone.keyframe_insert('location', frame=frame, group=bone.name)
    bone.location = base




def make_pose_action(name, bone_name, axis, amount):
    """Natural-rest pose clip: frame 1 must equal the shared reference pose
    (Animaze validates every clip's first frame against idle1), then ramps
    into the held pose."""
    bone = armature.pose.bones.get(bone_lookup.get(bone_name.lower(), bone_name))
    if not bone:
        return
    action = bpy.data.actions.new(name)
    animaze_actions.append(action)
    armature.animation_data_create()
    armature.animation_data.action = action
    bone.rotation_mode = 'XYZ'
    base = REST_REF.get(bone.name, bone.rotation_euler.copy())  # D7: canonical rest
    for frame, factor in ((1, 0.0), (8, 1.0), (16, 1.0)):
        bone.rotation_euler = base.copy()
        bone.rotation_euler[axis] += amount * factor
        bone.keyframe_insert('rotation_euler', frame=frame, group=bone.name)
    bone.rotation_euler = base


rotation_clips = {
    'Head_L': ('hehead', 2, 0.30), 'Head_R': ('hehead', 2, -0.30),
    'Head_U': ('hehead', 1, -0.22), 'Head_D': ('hehead', 1, 0.22),
    'Head_Twist_L': ('hehead', 0, -0.20), 'Head_Twist_R': ('hehead', 0, 0.20),
    'Avatar_L': ('pebip01', 2, 0.18), 'Avatar_R': ('pebip01', 2, -0.18),
    'Avatar_Twist_L': ('pebip01', 0, -0.14), 'Avatar_Twist_R': ('pebip01', 0, 0.14),
    'LeftEye_L': ('faeyel', 2, 0.16), 'LeftEye_R': ('faeyel', 2, -0.16),
    'LeftEye_U': ('faeyel', 1, -0.12), 'LeftEye_D': ('faeyel', 1, 0.12),
    'RightEye_L': ('faeyer', 2, 0.16), 'RightEye_R': ('faeyer', 2, -0.16),
    'RightEye_U': ('faeyer', 1, -0.12), 'RightEye_D': ('faeyer', 1, 0.12),
    'MouthJaw_L': ('fajaw', 2, 0.10), 'MouthJaw_R': ('fajaw', 2, -0.10),
    'HandL_solo_L': ('fihandl', 2, 0.30), 'HandL_solo_R': ('fihandl', 2, -0.30),
    'HandL_solo_U': ('fihandl', 1, -0.25), 'HandL_solo_D': ('fihandl', 1, 0.25),
    'HandL_solo_Twist_L': ('fihandl', 0, -0.30), 'HandL_solo_Twist_R': ('fihandl', 0, 0.30),
    'HandR_solo_L': ('fihandr', 2, 0.30), 'HandR_solo_R': ('fihandr', 2, -0.30),
    'HandR_solo_U': ('fihandr', 1, -0.25), 'HandR_solo_D': ('fihandr', 1, 0.25),
    'HandR_solo_Twist_L': ('fihandr', 0, -0.30), 'HandR_solo_Twist_R': ('fihandr', 0, 0.30),
    'LeftEar_U': ('hehead', 0, 0.025), 'LeftEar_D': ('hehead', 0, -0.025),
    'RightEar_U': ('hehead', 0, -0.025), 'RightEar_D': ('hehead', 0, 0.025),
    'IdleEar_L': ('hehead', 2, 0.015), 'IdleEar_R': ('hehead', 2, -0.015),
}
for clip_name, (clip_bone, axis, amount) in rotation_clips.items():
    make_rotation_action(clip_name, clip_bone, axis, amount)

finger_bones = {
    'FingerL0': 'fithumbl1', 'FingerL1': 'fifingerl1', 'FingerL2': 'forobearml2',
    'FingerL3': 'forobearml3', 'FingerL4': 'forobearml4',
    'FingerR0': 'fithumbr1', 'FingerR1': 'fifingerr1', 'FingerR2': 'forobearmr2',
    'FingerR3': 'forobearmr3', 'FingerR4': 'forobearmr4',
}
for prefix, finger_bone in finger_bones.items():
    make_rotation_action(prefix + '_ext', finger_bone, 1, -0.25)
    make_rotation_action(prefix + '_flex', finger_bone, 1, 0.45)

# ---- BONE-DRIVEN FACE (FaceRig-style): the Standard animtree discovers
# these clips by NAME from the Animations folder, replacing the broken
# blendshape pipeline entirely. Axis findings: eyelid open/close = axis 0
# (lab-verified); jaw down = axis 1 positive (proven by TongueOut_D clip).
LIP = 'falipcorners'; LTOP = 'faliptop'; LBOT = 'falipbottom'; NOSE = 'fanose'
BRL = 'faeyebrowl'; BRR = 'faeyebrowr'
LT, LB, RT, RB = 'faeyelidltop', 'faeyelidlbot', 'faeyelidrtop', 'faeyelidrbot'

# Jaw-open direction lives ONLY in the config (sign of jaw_open.amount). Every
# jaw-open literal below derives from it via JW() so a single config flip turns
# the whole viseme/mouth family around, and family variants stay byte-identical
# to MouthOpen (Law 5). JW() with no arg = full open (exactly MouthOpen's value);
# JW(v) = partial open of magnitude v in the configured direction.
JAWB, JAWAX = AX['jaw_open']['bone'], AX['jaw_open']['axis']
JAWO = AX['jaw_open']['amount']

def JW(v=None):
    return (JAWB, JAWAX, JAWO if v is None else math.copysign(v, JAWO))

def make_face_action(name, moves, held=frozenset()):
    # JAWTEST: `held` = set of (bone_name, axis) whose channel is pinned at its
    # full amount on EVERY frame (incl. frame 1). Animaze validates MouthOpen_*
    # variants' reference frame (frame 1) against MouthOpen's HELD OPEN pose,
    # and layers the variant relative to that reference; the jaw must therefore
    # START open in every MouthOpen-family variant.
    action = bpy.data.actions.new(name)
    animaze_actions.append(action)
    armature.animation_data_create()
    armature.animation_data.action = action
    bases = {}
    for bone_name, axis, amount in moves:
        bone = armature.pose.bones.get(bone_lookup.get(bone_name.lower(), bone_name))
        if not bone:
            continue
        bone.rotation_mode = 'XYZ'
        bases[bone_name] = REST_REF.get(bone.name, bone.rotation_euler.copy())  # D7: canonical rest
    for frame, factor in ((1, 0.0), (8, 1.0), (16, 1.0)):
        per_bone = {}
        for bone_name, axis, amount in moves:
            if bone_name not in bases:
                continue
            e = per_bone.setdefault(bone_name, bases[bone_name].copy())
            e[axis] += amount * (1.0 if (bone_name, axis) in held else factor)
        for bone_name, e in per_bone.items():
            bone = armature.pose.bones.get(bone_lookup.get(bone_name.lower(), bone_name))
            bone.rotation_euler = e
            bone.keyframe_insert('rotation_euler', frame=frame, group=bone.name)
    for bone_name, axis, amount in moves:
        bone = armature.pose.bones.get(bone_lookup.get(bone_name.lower(), bone_name))
        if bone and bone_name in bases:
            bone.rotation_euler = bases[bone_name]

make_face_action('MouthOpen', [(AX['jaw_open']['bone'], AX['jaw_open']['axis'], AX['jaw_open']['amount'])])
make_face_action('LeftEyeClosed', [(LT, AX['lid_top']['axis'], AX['lid_top']['amount']), (LB, AX['lid_bot']['axis'], AX['lid_bot']['amount'])])
make_face_action('RightEyeClosed', [(RT, AX['lid_top']['axis'], AX['lid_top']['amount']), (RB, AX['lid_bot']['axis'], AX['lid_bot']['amount'])])

# ---- THE OTHER 50 MOVING PARTS: full FaceRig-style clip set ----
# Conservative amplitudes; axis conventions from the labs (lids/jaw axis0).

_face_set = {
    # eyebrows (classic set; the animtree runs the old system)
    'LeftEyebrow_U':  [(BRL, 0, -0.35)], 'RightEyebrow_U':  [(BRR, 0, -0.35)],
    'LeftEyebrow_D':  [(BRL, 0,  0.28)], 'RightEyebrow_D':  [(BRR, 0,  0.28)],
    'LeftEyebrow_U_ext': [(BRL, 0, -0.5)], 'RightEyebrow_U_ext': [(BRR, 0, -0.5)],
    'LeftEyebrow_D_ext': [(BRL, 0,  0.38)], 'RightEyebrow_D_ext': [(BRR, 0,  0.38)],
    # eye extremes
    'LeftEyeWideOpen':  [(LT, 0, -0.5), (LB, 0,  0.2)],
    'RightEyeWideOpen': [(RT, 0, -0.5), (RB, 0,  0.2)],
    'LeftEyeSquint':    [(LT, 0,  0.5), (LB, 0, -0.25)],
    'RightEyeSquint':   [(RT, 0,  0.5), (RB, 0, -0.25)],
    # nose / cheeks
    'Nose_U': [(NOSE, 0, -0.3)], 'Nose_D': [(NOSE, 0, 0.3)],
    'CheekPuff_L': [(LIP, 1,  0.18)], 'CheekPuff_R': [(LIP, 1, -0.18)],
    # mouth corners & lips
    'MouthClosedLeft_U':  [(LIP, 0, -0.25), (LIP, 2,  0.12)],
    'MouthClosedRight_U': [(LIP, 0, -0.25), (LIP, 2, -0.12)],
    'MouthClosedLeft_D':  [(LIP, 0,  0.22), (LIP, 2,  0.12)],
    'MouthClosedRight_D': [(LIP, 0,  0.22), (LIP, 2, -0.12)],
    'MouthClosedLeft_teethCovered_U':  [(LTOP, 0,  0.2)],
    'MouthClosedRight_teethCovered_U': [(LTOP, 0,  0.2)],
    'MouthOpenLeft_U':  [(LIP, 0, -0.25), (LIP, 2,  0.12), JW()],
    'MouthOpenRight_U': [(LIP, 0, -0.25), (LIP, 2, -0.12), JW()],
    'MouthOpenLeft_D':  [(LIP, 0,  0.22), (LIP, 2,  0.12), JW()],
    'MouthOpenRight_D': [(LIP, 0,  0.22), (LIP, 2, -0.12), JW()],
    'MouthOpenLeft_teethCovered_U':  [(LTOP, 0, 0.2), JW()],
    'MouthOpenRight_teethCovered_U': [(LTOP, 0, 0.2), JW()],
    'Mouth_U': [(LTOP, 0, -0.28)],
    'Mouth_lipPress': [(LTOP, 0, 0.15), (LBOT, 0, -0.15)],
    'Mouth_unveilledTeeth_U': [(LTOP, 0, -0.35)],
    'Mouth_unveilledTeeth_D': [(LBOT, 0,  0.35)],
    'Mouth_pursedLips_Mid': [(LIP, 1, 0.3)],
    'Mouth_pursedLips_L':   [(LIP, 1, 0.25), (LIP, 2,  0.1)],
    'Mouth_pursedLips_R':   [(LIP, 1, 0.25), (LIP, 2, -0.1)],
    'MouthOpen_pursedLips_Mid': [(LIP, 1, 0.3), JW()],
    'MouthOpen_pursedLips_L':   [(LIP, 1, 0.25), (LIP, 2,  0.1), JW()],
    'MouthOpen_pursedLips_R':   [(LIP, 1, 0.25), (LIP, 2, -0.1), JW()],
    'MouthJaw_F': [JW(0.08)],
    'MouthClosed_TongueOut': [JW(0.10)],
    'MouthOpen_TongueOut':   [JW()],
    # visemes
    'viseme_AA': [JW(0.30)], 'viseme_AH': [JW(0.24)],
    'viseme_AO': [(LIP, 1, 0.22), JW(0.16)],
    'viseme_AW_OW': [(LIP, 1, 0.26), JW(0.18)],
    'viseme_OY_UH_UW': [(LIP, 1, 0.3), JW(0.10)],
    'viseme_EH_AE': [(LIP, 0, -0.16), JW(0.14)],
    'viseme_IH_AY': [(LIP, 0, -0.14), JW(0.10)],
    'viseme_EY':   [(LIP, 0, -0.22), JW(0.08)],
    'viseme_Y_IY': [(LIP, 0, -0.22), JW(0.06)],
    'viseme_R_ER': [(LIP, 1, 0.16), JW(0.10)],
    'viseme_L':    [JW(0.14)],
    'viseme_W':    [(LIP, 1, 0.3)],
    'viseme_M_P_B': [(LTOP, 0, 0.16), (LBOT, 0, -0.18)],
    'viseme_N_NG_DH': [JW(0.10)],
    'viseme_CH_J_SH': [(LIP, 1, 0.2), JW(0.08)],
    'viseme_FV': [(LTOP, 0, 0.12), (LBOT, 0, -0.14)],
    'viseme_S':  [(LIP, 0, -0.12), JW(0.06)],
    'viseme_TH': [JW()],
    'lipsync_F':  [(LTOP, 0, 0.12), (LBOT, 0, -0.14)],
    'lipsync_L':  [JW(0.14)],
    'lipsync_TH': [JW()],
    'lipsync_Y':  [(LIP, 0, -0.22), JW(0.06)],
}
for _name, _moves in _face_set.items():
    # JAWTEST: MouthOpen-family variants must START with the jaw already at
    # MouthOpen's held open pose (Animaze validates their frame 1 against it
    # and layers them on the open mouth). Pin the jaw channel for exactly the
    # clips Animaze family-checks: every MouthOpen* pose variant except the
    # parent itself.
    _held = {(JAWB, JAWAX)} if (_name.startswith('MouthOpen') and _name != 'MouthOpen') else frozenset()
    make_face_action(_name, _moves, held=_held)

# eye close-squint combo (animtree: "has eye close squint animation")
make_face_action('LeftEyeClosed_Squint',  [(LT, 0, 1.0), (LB, 0, -0.65)])
make_face_action('RightEyeClosed_Squint', [(RT, 0, 1.0), (RB, 0, -0.65)])

# the one hand clip the hand system asks for
make_rotation_action('HandL_closeUp_L', 'fihandl', 2, 0.20)
make_rotation_action('HandL_closeUp_Mid', 'fihandl', 2, 0.02)
make_rotation_action('HandL_closeUp_R', 'fihandl', 2, -0.20)

make_location_action('Avatar_B', 'pebip01', 0, -0.10)
make_location_action('Avatar_F', 'pebip01', 0, 0.10)
make_location_action('Avatar_U', 'pebip01', 2, 0.10)
make_location_action('Avatar_D', 'pebip01', 2, -0.10)
# Slow breathing idle: one gentle 96-frame cycle (~4s) instead of the
# seasick 16-frame sway or a dead statue.
def make_breath_action(name, bone_name, axis, amount, length=96):
    bone = armature.pose.bones.get(bone_lookup.get(bone_name.lower(), bone_name))
    if not bone:
        return
    action = bpy.data.actions.new(name)
    animaze_actions.append(action)
    armature.animation_data_create()
    armature.animation_data.action = action
    bone.rotation_mode = 'XYZ'
    base = bone.rotation_euler.copy()
    for frame, factor in ((1, 0.0), (length // 2, 1.0), (length, 0.0)):
        bone.rotation_euler = base.copy()
        bone.rotation_euler[axis] += amount * factor
        bone.keyframe_insert('rotation_euler', frame=frame, group=bone.name)
    bone.rotation_euler = base

make_breath_action('idle1', AX['breath']['bone'], AX['breath']['axis'], AX['breath']['amount'], length=AX['breath'].get('frames', 96))
make_pose_action('idle_naturalPose_L', 'bibicepl', AX['arm_down']['axis'], -AX['arm_down']['amount'])
make_pose_action('idle_naturalPose_R', 'bibicepr', AX['arm_down']['axis'], AX['arm_down']['amount'])
make_rotation_action('MouthClosed_TongueOut_L', 'fajaw', 2, 0.04)
make_rotation_action('MouthClosed_TongueOut_R', 'fajaw', 2, -0.04)
make_rotation_action('MouthClosed_TongueOut_U', 'fajaw', 1, -0.04)
make_rotation_action('MouthClosed_TongueOut_D', 'fajaw', 1, 0.04)
make_rotation_action('MouthOpen_TongueOut_L', 'fajaw', 2, 0.05)
make_rotation_action('MouthOpen_TongueOut_R', 'fajaw', 2, -0.05)
make_rotation_action('MouthOpen_TongueOut_U', 'fajaw', 1, -0.05)
make_rotation_action('MouthOpen_TongueOut_D', 'fajaw', 1, 0.05)
armature.animation_data.action = source_action
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

# Stance fix: the GLB's static pose hangs the feet en pointe (the "flying,
# toes-down" look). Bake EQ's OWN authored flat-foot stance into the export.
# RENDER-VERIFIED (2026-07-18): a single-axis hand rotation (the old foot_flat
# 0.75) only planted the toe-pads — the heel stayed off the floor. EQ's idle clip
# (o01) rotates each foot ~73-83 deg on local Y plus small X/Z, and the L/R values
# DIFFER; lifting those exact per-foot eulers is what actually drops the heel to
# the ground. config foot_pose carries the extracted values (keys starting with
# '_' are metadata). Applied AFTER armor authoring so the boot geometry rides the
# foot bones, and BEFORE the pose snapshot so grounding + every export inherit it.
_fp = AX.get('foot_pose')
if _fp:
    from mathutils import Euler as _Euler
    for _fb, _e in _fp.items():
        if _fb.startswith('_'):
            continue
        _fpb = armature.pose.bones.get(bone_lookup.get(_fb, _fb))
        if _fpb:
            _fpb.rotation_mode = 'XYZ'
            _fpb.rotation_euler = _Euler(_e, 'XYZ')
    bpy.context.view_layer.update()
    # The stance IS the rest pose (the GLB ships no animations, so its static
    # node transforms became the edit-bone rest on import). A pose-bone
    # rotation never reaches the FBX bind pose, so bake it: freeze the
    # deformation into every mesh, re-rest the armature, rebind. After this
    # the pose is identity again, so clip bases and frame-1 validation are
    # untouched, and grounding/preview/export all see planted feet.
    for _ob in [o for o in bpy.data.objects if o.type == 'MESH']:
        _mods = [m for m in _ob.modifiers if m.type == 'ARMATURE' and m.object == armature]
        if not _mods:
            continue
        with bpy.context.temp_override(object=_ob, active_object=_ob, selected_objects=[_ob]):
            for _m in list(_mods):
                bpy.ops.object.modifier_apply(modifier=_m.name)
        _nm = _ob.modifiers.new("Armature", 'ARMATURE')
        _nm.object = armature
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    print("EQ FOOT POSE baked into rest pose:", _fp)

for pb in armature.pose.bones:
    POSE_SNAPSHOT[pb.name] = pb.matrix_basis.copy()


# Studio preview.
world = bpy.data.worlds.new("Maskoi World")
bpy.context.scene.world = world
world.color = (0.006, 0.012, 0.02)

def add_area(name, location, energy, size, color):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.shape = 'DISK'
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (0, math.radians(90), 0)

add_area("Key", (8, -5, 6), 1800, 5, (0.72, 0.88, 1.0))
add_area("Emerald Fill", (6, 5, 3), 1300, 5, (0.30, 1.0, 0.55))
add_area("Rim", (-6, 0, 5), 1700, 4, (0.25, 0.50, 1.0))

camera_data = bpy.data.cameras.new("Camera")
camera = bpy.data.objects.new("Camera", camera_data)
bpy.context.collection.objects.link(camera)
bpy.context.scene.camera = camera
camera.location = (13.5, 0, 0.25)
camera.rotation_euler = (Vector((0, 0, 0.25)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.lens = 60

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1000
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUT_PREVIEW)
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = 1.25

# ============ SINGLE-ATLAS BAKE ============
# Animaze's FBX importer applies only ONE texture per mesh (slot 0's), which
# scrambled every multi-material build. Merge all 30 body regions into one
# texture atlas + one material, remapping UVs into per-region cells. The
# actual atlas pixels are composed by postprocess_textures.py from the
# manifest written here; the build only needs the geometry mapping.
import json
CELL = 256
GRID_COLS = 8  # 8x4 grid of 256 = 2048x1024, power-of-two for the KTX converter
mats_order = [m.name if m else "" for m in body.data.materials]
n_cells = len(mats_order)
GRID_ROWS = (n_cells + GRID_COLS - 1) // GRID_COLS
ATLAS_W, ATLAS_H = GRID_COLS * CELL, GRID_ROWS * CELL

manifest = []
for index, mat in enumerate(body.data.materials):
    src = None
    if mat and mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                nm = node.image.name
                nm = nm if nm.lower().endswith('.png') else nm + '.png'
                src = nm
                break
    manifest.append({"slot": index, "material": mats_order[index],
                     "cell": [index % GRID_COLS, index // GRID_COLS],
                     "source": src})

inset = 16.0 / CELL  # match the 16px atlas gutters (mip-bleed guard)
for uv_layer in body.data.uv_layers:
    data = uv_layer.data
    for poly in body.data.polygons:
        cx = poly.material_index % GRID_COLS
        cy = poly.material_index // GRID_COLS
        for li in poly.loop_indices:
            u, v = data[li].uv
            u = min(max(u, 0.0), 1.0); v = min(max(v, 0.0), 1.0)
            u = inset + u * (1.0 - 2.0 * inset)
            v = inset + v * (1.0 - 2.0 * inset)
            data[li].uv = ((cx + u) * CELL / ATLAS_W,
                           1.0 - ((cy + (1.0 - v)) * CELL / ATLAS_H))

# stub atlas image (postprocess overwrites the shipped file with real pixels)
atlas_img = bpy.data.images.new("Maskoi Body Atlas", width=ATLAS_W, height=ATLAS_H, alpha=True)
atlas_img.generated_color = (0.5, 0.5, 0.5, 1.0)
atlas_mat = bpy.data.materials.new("Maskoi Body Atlas")
atlas_mat.use_nodes = True
direct_image_link(atlas_mat, atlas_img)
absdf = next(n for n in atlas_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
# Iksar hide is organic, NOT metal. Metallic 0.25 made Animaze render him glassy/
# reflective and washed the scaled-skin albedo to pale grey ("made of glass").
# Skin = 0 metallic, high roughness (matte with only a faint scale sheen).
absdf.inputs['Metallic'].default_value = 0.0
absdf.inputs['Roughness'].default_value = 0.82
body.data.materials.clear()
body.data.materials.append(atlas_mat)
for poly in body.data.polygons:
    poly.material_index = 0

# EQ character/armor is fully opaque; the only alpha in these textures is EQ's
# env-shine mask (flattened to 255 in postprocess). Blender 4.5 defaults any
# alpha-bearing image material to HASHED blend, which dithers the plates into a
# glassy/translucent look. Force OPAQUE so nothing ghosts through the armor.
for _m in bpy.data.materials:
    try:
        _m.blend_method = 'OPAQUE'
    except (AttributeError, TypeError):
        pass

with open(OUT_DIR / "atlas_manifest.json", "w") as fh:
    json.dump({"cell": CELL, "cols": GRID_COLS, "rows": GRID_ROWS,
               "atlas": "Maskoi_Body_Atlas.png", "dye": CFG.get("dye", "authentic"),
               "tiles_dir": CFG["armor_tiles_dir"], "armor_set": CFG["armor_set"],
               "race_token": CFG["race_token"],
               "entries": manifest}, fh, indent=1)
print("ATLAS: ", n_cells, "cells", ATLAS_W, "x", ATLAS_H)
# ============ END ATLAS BAKE ============

restore_pose()

# Ground the avatar: EQ authored the rig hip-centered, leaving the feet ~3.9
# units below origin, so Animaze floats him. Lift the whole rig so the lowest
# point (claw tips) sits exactly at z=0.
#
# CRITICAL: measure in the REST pose, not the current (posed) state. The FBX
# bind ships the REST pose, and the feet are never moved by a clip, so Animaze
# displays them at their REST position. Grounding the arms-down posed state left
# the rest-pose feet ~0.79 units high -> he floated (scaled: 0.79 * export_scale
# ~= 0.24 in-app). Switch to REST for the measurement, then restore POSE.
_prev_pose_position = armature.data.pose_position
armature.data.pose_position = 'REST'
bpy.context.view_layer.update()
_ground_deps = bpy.context.evaluated_depsgraph_get()
_lowest = 1e9
for _o in bpy.data.objects:
    if _o.type != 'MESH':
        continue
    _ev = _o.evaluated_get(_ground_deps)
    _me = _ev.to_mesh()
    for _v in _me.vertices:
        z = (_o.matrix_world @ _v.co).z
        if z < _lowest:
            _lowest = z
    _ev.to_mesh_clear()
armature.data.pose_position = _prev_pose_position
bpy.context.view_layer.update()
armature.location.z -= _lowest
bpy.context.view_layer.update()
print("GROUNDED (rest pose): lifted by", round(-_lowest, 3))

# Normalize export scale: EQ units make him ~7m tall in Animaze (feet dangle,
# toes-down hang). Scale the FBX export to a human-standard height.
_highest = -1e9
for _o in bpy.data.objects:
    if _o.type != 'MESH':
        continue
    _ev = _o.evaluated_get(_ground_deps)
    _me = _ev.to_mesh()
    for _v in _me.vertices:
        z = (_o.matrix_world @ _v.co).z
        if z > _highest:
            _highest = z
    _ev.to_mesh_clear()
EXPORT_SCALE = CFG.get("target_height_m", 1.85) / max(_highest, 0.01)
print("EXPORT SCALE:", round(EXPORT_SCALE, 4), "(height", round(_highest, 2), "->", CFG.get("target_height_m", 1.85), "m)")

# Generated images lose their pixels when a .blend reloads unless packed.
for img in bpy.data.images:
    if img.name.startswith("Maskoi") and not img.filepath:
        try:
            img.pack()
        except Exception:
            pass

bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.scene.objects:
    if obj.type in {'ARMATURE', 'MESH'}:
        obj.select_set(True)
bpy.context.view_layer.objects.active = armature

# Animaze does not follow Blender's conventional .fbm companion directory.
# Its documented FBX pipeline requires PNG/TGA sources in a literal sibling
# Textures/ directory. Materialize only images actually used by the avatar,
# then replace every shader reference with a genuinely file-backed image.
# save_render() encodes textures through the scene view transform; keep it
# honest sRGB with no film look or exposure push.
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0.0
try:
    scene.view_settings.view_transform = 'Standard'
except Exception:
    pass

used_images = set()
for obj in bpy.context.selected_objects:
    if obj.type != 'MESH':
        continue
    for material in obj.data.materials:
        if material and material.use_nodes:
            bsdf = next((node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
            if bsdf and bsdf.inputs['Base Color'].links:
                node = bsdf.inputs['Base Color'].links[0].from_node
                if node.type == 'TEX_IMAGE' and node.image:
                    used_images.add(node.image)
image_replacements = {}
for image in used_images:
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in image.name)
    target = TEXTURE_DIR / f"{safe_name}.png"
    image.save_render(str(target))
    image_replacements[image] = bpy.data.images.load(str(target), check_existing=False)

for obj in bpy.context.selected_objects:
    if obj.type != 'MESH':
        continue
    for material in obj.data.materials:
        if not material or not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image in image_replacements:
                node.image = image_replacements[node.image]

bpy.ops.export_scene.fbx(
    filepath=str(OUT_FBX),
    use_selection=True,
    global_scale=EXPORT_SCALE,
    add_leaf_bones=False,
    bake_anim=False,
    path_mode='RELATIVE',
    embed_textures=False,
    use_armature_deform_only=True,
)

# Animaze discovers required motion clips from a sibling Animations folder; it
# does not use multiple embedded stacks in the avatar FBX for its animtree.
bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
for action in animaze_actions:
    armature.animation_data.action = action
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = max(16, int(action.frame_range[1]))
    bpy.ops.export_scene.fbx(
        filepath=str(ANIM_DIR / f"{action.name}.fbx"),
        use_selection=True,
        global_scale=EXPORT_SCALE,
        object_types={'ARMATURE'},
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=False,
        bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0,
        path_mode='STRIP',
        use_armature_deform_only=True,
    )
armature.animation_data.action = source_action
bpy.context.scene.frame_set(1)
restore_pose()
bpy.ops.render.render(write_still=True)
camera.location = (7.2, 0, 1.55)
camera.rotation_euler = (Vector((0, 0, 1.55)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.lens = 68
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.filepath = str(OUT_PORTRAIT)
bpy.ops.render.render(write_still=True)

# Neutral-light verification renders: honest colors, no film look.
for obj in [o for o in bpy.context.scene.objects if o.type == 'LIGHT']:
    bpy.data.objects.remove(obj, do_unlink=True)
def add_neutral(name, location, energy):
    data = bpy.data.lights.new(name, 'POINT')
    data.energy = energy
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
add_neutral("N1", (6, -5, 5), 3000)
add_neutral("N2", (-5, -3, 5), 1800)
add_neutral("N3", (0, 6, 3), 1200)
add_neutral("N4", (5, 4, 1), 1000)
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0.2
camera.location = (10.5, 0, 0.2)
camera.rotation_euler = (Vector((0, 0, 0.2)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.lens = 55
scene.render.resolution_x = 900
scene.render.resolution_y = 1100
scene.render.filepath = str(OUT_DIR / "MASKOI-neutral.png")
bpy.ops.render.render(write_still=True)
head_target = Vector((-0.10, 0, 2.77))
camera.location = head_target + Vector((1, -0.35, 0.10)).normalized() * 2.4
camera.rotation_euler = (head_target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.lens = 62
scene.render.resolution_x = 800
scene.render.resolution_y = 800
scene.render.filepath = str(OUT_DIR / "MASKOI-neutral-head.png")
bpy.ops.render.render(write_still=True)
print("SAVED", OUT_BLEND, OUT_FBX, OUT_PREVIEW, OUT_PORTRAIT)

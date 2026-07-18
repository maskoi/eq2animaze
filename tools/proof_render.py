import bpy
from mathutils import Vector

SCRATCH = "C:/Users/Raphael/AppData/Local/Temp/claude/C--Users-Raphael-Desktop-Maskoi-Avatar-Maskoi-Armored-V9-CLEAN/8dc251b0-c7cb-4e96-aa24-e15d30506664/scratchpad/"

# repoint every Maskoi texture at the calibrated pixels
atlas = bpy.data.images.load(SCRATCH + "Maskoi_Body_Atlas.png")
plate = None
try:
    plate = bpy.data.images.load(SCRATCH + "plate_calibrated.png")
except Exception:
    pass
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            n = node.image.name.lower()
            if "atlas" in n:
                node.image = atlas
            elif plate and ("plate" in n or "emerald" in n):
                node.image = plate

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    arm.animation_data.action = None
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

hh = arm.matrix_world @ arm.pose.bones["hehead"].head
print("head z:", round(hh.z, 2))

scene = bpy.context.scene
cd = bpy.data.cameras.new("c"); co = bpy.data.objects.new("c", cd)
scene.collection.objects.link(co); scene.camera = co
t = Vector((0, 0, hh.z - 1.6))          # chest center
co.location = t + Vector((-4.6, 0, 0.4)) # model faces -X
co.rotation_euler = (t - co.location).to_track_quat('-Z', 'Y').to_euler()

sun = bpy.data.lights.new("s", type='SUN'); so = bpy.data.objects.new("s", sun)
scene.collection.objects.link(so)
so.rotation_euler = (1.0, 0.3, 1.3)
sun.energy = 3.0
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 560
scene.render.resolution_y = 660
scene.view_settings.view_transform = 'Standard'
scene.render.filepath = SCRATCH + "proof_v55.png"
bpy.ops.render.render(write_still=True)
print("PROOF RENDERED")

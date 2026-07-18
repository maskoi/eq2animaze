import bpy, math, sys
from mathutils import Vector

OUT = "C:/Users/Raphael/AppData/Local/Temp/claude/C--Users-Raphael-Desktop-Maskoi-Avatar-Maskoi-Armored-V9-CLEAN/8dc251b0-c7cb-4e96-aa24-e15d30506664/scratchpad/footlab/"

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')

# Clear action so fcurves don't override manual pose (axis-lab rule)
if arm.animation_data:
    arm.animation_data.action = None
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

# Camera: side profile of the lower legs (feet close-up)
fl = arm.pose.bones["bofootl"]
foot_world = arm.matrix_world @ fl.matrix.translation
print("FOOT WORLD:", [round(c, 3) for c in foot_world])

scene = bpy.context.scene
cam_data = bpy.data.cameras.new("LabCam")
cam = bpy.data.objects.new("LabCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# place camera to the model's side (+X world), looking at the feet
target = foot_world.copy()
target.z += 0.55
cam.location = target + Vector((5.5, 0.0, 0.3))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

sun = bpy.data.lights.new("LabSun", type='SUN')
sun_obj = bpy.data.objects.new("LabSun", sun)
scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (0.9, 0.2, 0.5)
sun.energy = 4

scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.view_settings.view_transform = 'Standard'

def snap(tag):
    scene.render.filepath = OUT + tag + ".png"
    bpy.ops.render.render(write_still=True)
    print("WROTE", tag)

def set_foot(axis, val):
    for bname in ("bofootl", "bofootr"):
        pb = arm.pose.bones[bname]
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0.0, 0.0, 0.0)
        if axis is not None:
            pb.rotation_euler[axis] = val
    bpy.context.view_layer.update()

set_foot(None, 0)
snap("baseline")
for axis in (0, 1, 2):
    for sign, tag in ((0.5, "pos"), (-0.5, "neg")):
        set_foot(axis, sign)
        snap(f"ax{axis}_{tag}")
set_foot(None, 0)
print("LAB DONE")

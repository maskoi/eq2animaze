import bpy, math

ANIM = "C:/Users/Raphael/Desktop/Maskoi Avatar/eq2animaze/work/IMPORT-ONLY-Maskoi-Armored-V51/Animations/"
bpy.ops.wm.read_factory_settings(use_empty=True)

for clip in ("MouthOpen", "MouthOpenLeft_U", "viseme_AA"):
    before = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=ANIM + clip + ".fbx")
    new_actions = [a for a in bpy.data.actions if a not in before]
    for act in new_actions:
        for fc in act.fcurves:
            if "fajaw" in fc.data_path.lower() and "rotation" in fc.data_path:
                keys = [(round(k.co[0], 1), round(math.degrees(k.co[1]), 3)) for k in fc.keyframe_points]
                print(f"CLIP {clip} | action {act.name} | {fc.data_path.split(chr(34))[1]} {fc.data_path.rsplit('.',1)[-1]}[{fc.array_index}] deg -> {keys}")

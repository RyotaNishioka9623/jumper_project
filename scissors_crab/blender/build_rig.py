"""Build an animatable Jumper rig in Blender from the training model.

    blender --background --python scissors_crab/blender/build_rig.py -- \
        --out scissors_crab/blender/jumper_rig.blend [--render preview.png]

The rig is read from `assets/jumper/jumper.xml`, the same MJCF the trainer loads, so
the kinematics, the joint axes and the joint ranges are the ones a policy is scored
against. (The URDF disagrees with it on some ranges, e.g. `LM_J0_joint`; the MJCF
wins because it is what training reads.)

Every MJCF body becomes an Empty at its `pos` under its parent. A body that carries a
joint is named after the joint (`LF_J0`, ...): it rotates about that one axis only,
the other two are locked, and a Limit Rotation constraint holds the joint range.
Rotating it in the viewport is moving that servo. Visual meshes hang under the bodies.

The base stays fixed at the standing height. The real base pose is solved from the
joint angles when the keyframes are converted (`keyframes_to_npz.py`), so what is
animated here is joint angles only.

Frame 1 is keyed at `HOME`, the pose every gesture starts and ends in.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[2]
MJCF = REPO / "assets" / "jumper" / "jumper.xml"
CONSTANTS = REPO / "tasks" / "jumper" / "common" / "constants.py"
FPS = 30
AXIS_INDEX = {(1, 0, 0): 0, (0, 1, 0): 1, (0, 0, 1): 2}


def read_home() -> tuple[dict[str, float], float]:
    """`HOME` and `STAND_Z` from constants.py, parsed as text: Blender's Python has no
    mjlab, and the constants file is the one place they are written down."""
    text = CONSTANTS.read_text()
    block = re.search(r"^HOME: dict\[str, float\] = \{(.*?)^\}", text, re.DOTALL | re.MULTILINE).group(1)
    home = {k: float(v) for k, v in re.findall(r'"(\w+_joint)":\s*(-?[\d.]+)', block)}
    stand_z = float(re.search(r"^STAND_Z = ([\d.]+)", text, re.MULTILINE).group(1))
    return home, stand_z


def vec(text: str | None, n: int = 3) -> tuple[float, ...]:
    return tuple(float(x) for x in text.split()) if text else (0.0,) * n


def material(rgba: tuple[float, ...]) -> bpy.types.Material:
    name = "jumper_" + "_".join(f"{c:.3f}" for c in rgba)
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = rgba
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = 0.45
    return mat


def import_stl(path: Path) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.wm.stl_import(filepath=str(path))
    return bpy.context.selected_objects[0]


def link(obj: bpy.types.Object, coll: bpy.types.Collection) -> None:
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)


def build(home: dict[str, float], stand_z: float) -> list[bpy.types.Object]:
    root = ET.parse(MJCF).getroot()
    meshdir = MJCF.parent / (root.find("compiler").get("meshdir") or "")
    meshes = {m.get("name"): meshdir / m.get("file") for m in root.iter("mesh")}

    rig = bpy.data.collections.new("jumper_rig")
    bpy.context.scene.collection.children.link(rig)
    geo = bpy.data.collections.new("jumper_meshes")
    rig.children.link(geo)

    top = bpy.data.objects.new("jumper_root", None)
    top.empty_display_type = "CUBE"
    top.empty_display_size = 0.02
    top.location = (0.0, 0.0, stand_z)
    rig.objects.link(top)

    joints: list[bpy.types.Object] = []

    def walk(body: ET.Element, parent: bpy.types.Object) -> None:
        joint = body.find("joint")
        if joint is not None and joint.get("type") == "free":
            joint = None  # the floating base: posed by the converter, not animated
        name = joint.get("name").removesuffix("_joint") if joint is not None else body.get("name")
        obj = bpy.data.objects.new(name, None)
        obj.parent = parent
        obj.location = vec(body.get("pos"))
        obj.empty_display_size = 0.015
        rig.objects.link(obj)

        if joint is not None:
            axis = tuple(round(a) for a in vec(joint.get("axis")))
            i = AXIS_INDEX[axis]
            lo, hi = vec(joint.get("range"), 2)
            obj.empty_display_type = "ARROWS"
            obj.rotation_mode = "XYZ"
            obj.lock_rotation = [k != i for k in range(3)]
            obj.lock_location = [True] * 3
            obj.lock_scale = [True] * 3
            # Limit Rotation works on angles within half a turn; the shoulders' J1
            # (-4.75..1.4 rad) goes past it, so those are clamped at export only.
            if -math.pi < lo and hi < math.pi:
                lim = obj.constraints.new("LIMIT_ROTATION")
                lim.owner_space = "LOCAL"
                for k, ax in enumerate("xyz"):
                    setattr(lim, f"use_limit_{ax}", True)
                    setattr(lim, f"min_{ax}", lo if k == i else 0.0)
                    setattr(lim, f"max_{ax}", hi if k == i else 0.0)
            obj["joint"] = joint.get("name")
            obj["axis"] = i
            obj["range"] = [lo, hi]
            obj.rotation_euler[i] = home[joint.get("name")]
            joints.append(obj)
        else:
            obj.empty_display_type = "PLAIN_AXES"
            obj.hide_select = body.get("name") != "base_link"

        for g in body.findall("geom"):
            if g.get("class") != "visual" or g.get("type") != "mesh":
                continue
            mesh_obj = import_stl(meshes[g.get("mesh")])
            mesh_obj.name = g.get("name")
            mesh_obj.parent = obj
            mesh_obj.data.materials.clear()
            mesh_obj.data.materials.append(material(vec(g.get("rgba"), 4)))
            mesh_obj.hide_select = True
            link(mesh_obj, geo)

        for child in body.findall("body"):
            walk(child, obj)

    walk(root.find("worldbody").find("body"), top)
    return joints


#: The face: two round 0.9-inch TFTs (docs/HARDWARE.md) on the display module's front
#: panel. The panel's outward normal and the centre of its front face, in the base
#: frame, measured from `display_module_link`'s mesh (area-weighted over the faces
#: with that normal). The eyes' spacing is not in the model: the panel is 107 mm wide
#: and the eyes are set symmetric on it.
PANEL_NORMAL = (0.8, 0.0, 0.6)
PANEL_CENTRE = (0.0764, 0.0, 0.0541)
EYE_RADIUS = 0.0229 / 2
EYE_SPACING = 0.052
EYES_DIR = REPO / "scissors_crab" / "assets" / "eyes"


def eye_material(side: str) -> bpy.types.Material:
    """Emission from an image: a still by default, an image sequence once a motion is
    imported (`import_motion.py` swaps the image)."""
    mat = bpy.data.materials.new(f"eye_{side}")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.name = "eye_image"
    tex.image = bpy.data.images.load(str(EYES_DIR / f"neutral_{side}.png"))
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.2
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emit.inputs["Color"])
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def add_eyes(rig: bpy.types.Collection) -> None:
    from mathutils import Matrix, Vector

    base = bpy.data.objects["base_link"]
    n = Vector(PANEL_NORMAL).normalized()
    up = (Vector((0, 0, 1)) - n * n.z).normalized()
    # The picture's x runs to the viewer's right, facing the robot: the robot's +y.
    x = Vector((0, 1, 0))
    rot = Matrix((x, up, n)).transposed()
    # R is the robot's right eye, at -y; its picture is drawn for the viewer's left.
    for side, y in (("R", -EYE_SPACING / 2), ("L", EYE_SPACING / 2)):
        bpy.ops.mesh.primitive_circle_add(vertices=64, radius=EYE_RADIUS, fill_type="NGON")
        eye = bpy.context.active_object
        eye.name = f"eye_{side}"
        uv = eye.data.uv_layers.new(name="UVMap")
        for loop in eye.data.loops:
            co = eye.data.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = (co.x / (2 * EYE_RADIUS) + 0.5, co.y / (2 * EYE_RADIUS) + 0.5)
        eye.data.materials.append(eye_material(side))
        eye.parent = base
        centre = Vector(PANEL_CENTRE) + Vector((0, y, 0)) + n * 0.0008
        eye.matrix_parent_inverse.identity()
        eye.matrix_basis = Matrix.Translation(centre) @ rot.to_4x4()
        eye.hide_select = True
        link(eye, rig)


def key_home(joints: list[bpy.types.Object]) -> None:
    for obj in joints:
        obj.keyframe_insert("rotation_euler", index=obj["axis"], frame=1)


def stage(stand_z: float) -> None:
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, 90
    scene.unit_settings.system = "METRIC"

    bpy.ops.mesh.primitive_plane_add(size=1.2, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "floor"
    floor.hide_select = True
    floor.data.materials.append(material((0.93, 0.93, 0.9, 1.0)))

    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = (0.95, -0.75, 0.55)
    scene.collection.objects.link(cam)
    aim = cam.constraints.new("TRACK_TO")
    target = bpy.data.objects.new("cam_target", None)
    target.location = (0.0, 0.0, stand_z)
    scene.collection.objects.link(target)
    aim.target = target
    scene.camera = cam

    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
    scene.collection.objects.link(sun)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("world")
    scene.world.color = (0.8, 0.82, 0.85)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("jumper_rig.blend"))
    ap.add_argument("--render", type=Path, help="also render frame 1 to this PNG")
    args = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    home, stand_z = read_home()
    joints = build(home, stand_z)
    add_eyes(bpy.data.collections["jumper_rig"])
    key_home(joints)
    stage(stand_z)
    bpy.context.view_layer.update()
    print(f"built {len(joints)} joints from {MJCF.relative_to(REPO)}")

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print(f"saved {out}")

    if args.render:
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_EEVEE"
        scene.render.resolution_x, scene.render.resolution_y = 960, 720
        scene.render.filepath = str(args.render.resolve())
        scene.frame_set(1)
        bpy.ops.render.render(write_still=True)
        print(f"rendered {args.render}")


if __name__ == "__main__":
    main()

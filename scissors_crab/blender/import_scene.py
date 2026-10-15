"""Bring an official Jumper scene (`.map`, from KingKongRobotics/jumper-design) into Blender
as the set the robot performs on.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/blender/import_scene.py -- \
        scissors_crab/external/maps/home.map --save scene_home.blend

A `.map` is a zip holding a MuJoCo scene (`scene.xml`): invisible collision boxes, and
the visible set as OBJ meshes with a material colour each. Only what is drawn is
brought over -- mesh geoms with a visible colour, and the ground plane -- placed as the
MJCF places them (body `pos`, geom `pos`/`euler`, radians). The OBJ files are already
in the body frame, Z up, so they import without an axis change. The map's own robot
and its props' physics are not used: the robot here is the rig, driven by a recorded
replay. The rig's grey studio floor is hidden in favour of the scene's ground.

The scene is the organizer's material; credit it where the video is published
("scene: KingKong Robotics jumper-design").
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector


def extract(map_path: Path) -> Path:
    """Unpack the .map next to itself (`<name>/`), refusing paths that leave it."""
    dest = map_path.with_suffix("")
    if (dest / "scene.xml").exists():
        return dest
    with zipfile.ZipFile(map_path) as z:
        for name in z.namelist():
            target = (dest / name).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise ValueError(f"{map_path}: {name} leaves the package")
        z.extractall(dest)
    return dest


def vec(text: str | None, n: int = 3) -> tuple[float, ...]:
    return tuple(float(x) for x in text.split()) if text else (0.0,) * n


def local(el: ET.Element) -> Matrix:
    m = Matrix.Translation(Vector(vec(el.get("pos"))))
    if el.get("euler"):
        m = m @ Euler(vec(el.get("euler")), "XYZ").to_matrix().to_4x4()
    if el.get("quat"):
        from mathutils import Quaternion
        m = m @ Quaternion(vec(el.get("quat"), 4)).to_matrix().to_4x4()
    return m


def material(name: str, rgba: tuple[float, ...], roughness: float) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = rgba
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build(root_dir: Path) -> int:
    root = ET.parse(root_dir / "scene.xml").getroot()
    mats = {m.get("name"): (vec(m.get("rgba"), 4), float(m.get("roughness", 0.8)))
            for m in root.iter("material")}
    meshes = {m.get("name"): root_dir / m.get("file") for m in root.iter("mesh")}

    coll = bpy.data.collections.new("scene")
    bpy.context.scene.collection.children.link(coll)
    count = 0

    def add_geom(g: ET.Element, frame: Matrix) -> None:
        nonlocal count
        mat_name = g.get("material")
        rgba = mats[mat_name][0] if mat_name in mats else vec(g.get("rgba"), 4)
        if g.get("type") == "plane":
            bpy.ops.mesh.primitive_plane_add(size=2.0 * vec(g.get("size"))[0])
            obj = bpy.context.active_object
        elif g.get("type") == "mesh" and rgba[3] > 0.0:
            bpy.ops.object.select_all(action="DESELECT")
            bpy.ops.wm.obj_import(filepath=str(meshes[g.get("mesh")]),
                                  forward_axis="Y", up_axis="Z")
            obj = bpy.context.selected_objects[0]
        else:
            return  # collision geometry: drawn by nothing
        obj.name = g.get("name") or f"scene_{count}"
        obj.matrix_world = frame @ local(g)
        obj.data.materials.clear()
        roughness = mats[mat_name][1] if mat_name in mats else 0.8
        obj.data.materials.append(material(f"scene_{mat_name or obj.name}", rgba, roughness))
        for c in obj.users_collection:
            c.objects.unlink(obj)
        coll.objects.link(obj)
        obj.hide_select = True
        count += 1

    def walk(el: ET.Element, frame: Matrix) -> None:
        for g in el.findall("geom"):
            add_geom(g, frame)
        for b in el.findall("body"):
            walk(b, frame @ local(b))

    walk(root.find("worldbody"), Matrix.Identity(4))
    return count


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("map", type=Path, help="a .map from jumper-design's library/maps")
    ap.add_argument("--save", type=Path, help="save the rig and the set as this .blend")
    args = ap.parse_args(argv)

    n = build(extract(args.map.resolve()))
    floor = bpy.data.objects.get("floor")
    if floor is not None:
        floor.hide_render = floor.hide_viewport = True
    print(f"placed {n} pieces of {args.map.name}")
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.save.resolve()))
        print(f"saved {args.save}")


if __name__ == "__main__":
    main()

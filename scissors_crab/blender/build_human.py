"""Build the human who plays janken with the crab: a CC0 Blender base mesh, dressed and rigged.

    blender --background --python scissors_crab/blender/build_human.py -- \
        --bundle scissors_crab/external/human-base-meshes/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend \
        --body male --out scissors_crab/renders/sets/human.blend

The body is Blender Studio's "Human Base Meshes" (CC0), realistic, male or female -- the
two share one topology and one set of sculpt face sets, which is what this script
relies on: the face sets split the body into parts down to each finger's phalanges, so
every joint is placed where two neighbouring parts meet (the centroid of the vertices
they share), and the rig fits the mesh exactly without a hand-placed metarig.

The rig is plain FK, deform bones only: spine, neck, head, clavicles, arms, five fingers
of three bones each, legs and toes. Weights are Blender's automatic (bone heat). Bone
names follow `<part>.<L|R>`, the body's own left and right.

"Clothes" are materials on face sets -- a T-shirt over the torso and upper arms,
trousers from the pelvis to the ankles, shoes, and hair on the top of the head -- so
the mesh stays one piece and deforms as one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

COLLECTIONS = {"male": "Body Male - Realistic", "female": "Body Female - Realistic"}
BODY = {"male": "GEO-body_male_realistic", "female": "GEO-body_female_realistic"}

#: Face-set ids, identified by position on the shared topology (body left is +X when the
#: body faces -Y). Pairs are (left, right).
HEAD, TORSO, ABDOMEN, PELVIS = 17, 1, 19, 18
UPPER_ARM, FOREARM, HAND = (21, 20), (12, 11), (9, 10)
THIGH, SHIN, FOOT = (24, 23), (15, 16), (14, 13)
#: Each finger, thumb to little, as its three phalanx face sets (the nail set is
#: skipped), left hand then right hand.
FINGERS = {
    "L": {"thumb": (80, 81, 82), "index": (76, 77, 78), "middle": (72, 73, 74),
          "ring": (68, 69, 70), "pinky": (64, 65, 66)},
    "R": {"thumb": (84, 85, 86), "index": (88, 89, 90), "middle": (92, 93, 94),
          "ring": (96, 97, 98), "pinky": (100, 101, 102)},
}

SKIN = (0.80, 0.60, 0.48, 1.0)
HAIR = (0.10, 0.08, 0.07, 1.0)
#: Outfit per body: shirt, trousers, socks.
OUTFITS = {
    "male": ((0.93, 0.93, 0.90, 1.0), (0.20, 0.27, 0.40, 1.0), (0.12, 0.12, 0.13, 1.0)),
    # Soft colours, kept clear of the skin tone: a butter-yellow top, light denim, white
    # socks. (A coral top read as bare skin.)
    "female": ((0.98, 0.86, 0.52, 1.0), (0.52, 0.62, 0.78, 1.0), (0.93, 0.93, 0.91, 1.0)),
}


def append_body(bundle: Path, body: str) -> bpy.types.Object:
    with bpy.data.libraries.load(str(bundle), link=False) as (_, dst):
        dst.collections = [COLLECTIONS[body]]
    coll = dst.collections[0]
    bpy.context.scene.collection.children.link(coll)
    obj = bpy.data.objects[BODY[body]]
    for m in list(obj.modifiers):
        obj.modifiers.remove(m)  # the multires sculpt levels: the base cage is enough here
    # Centre it on X; it faces -Y, Z up, feet at 0. Only the roots move: the eyes are
    # the body's children and would move twice.
    shift = Vector((-obj.location.x, 0.0, 0.0))
    for o in coll.all_objects:
        if o.parent is None:
            o.location += shift
    bpy.context.view_layer.update()
    return obj


class Parts:
    """Vertex sets and positions per face set, in world space at rest."""

    def __init__(self, obj: bpy.types.Object) -> None:
        me = obj.data
        mw = obj.matrix_world
        self.co = np.array([mw @ v.co for v in me.vertices])
        fs = [d.value for d in me.attributes[".sculpt_face_set"].data]
        self.sets: dict[int, set[int]] = {}
        self.face_set = np.array(fs)
        for poly, f in zip(me.polygons, fs):
            self.sets.setdefault(f, set()).update(poly.vertices)

    def seam(self, a: int, b: int) -> Vector:
        shared = self.sets[a] & self.sets[b]
        if len(shared) < 3:
            raise ValueError(f"face sets {a} and {b} do not meet")
        return Vector(self.co[list(shared)].mean(axis=0))

    def tip(self, f: int, away_from: Vector) -> Vector:
        """The vertex of set `f` furthest from `away_from`."""
        v = self.co[list(self.sets[f])]
        d = np.linalg.norm(v - np.array(away_from), axis=1)
        return Vector(v[np.argmax(d)])

    def centre(self, f: int) -> Vector:
        return Vector(self.co[list(self.sets[f])].mean(axis=0))


def joints(p: Parts) -> dict[str, tuple[Vector, Vector, str | None]]:
    """name -> (head, tail, parent)."""
    j: dict[str, tuple[Vector, Vector, str | None]] = {}
    hips = p.seam(PELVIS, ABDOMEN)
    pelvis_low = (p.seam(PELVIS, THIGH[0]) + p.seam(PELVIS, THIGH[1])) / 2
    chest = p.seam(ABDOMEN, TORSO)
    neck = p.seam(TORSO, HEAD)
    head_top = p.tip(HEAD, neck)
    j["hips"] = (pelvis_low, hips, None)
    j["spine"] = (hips, chest, "hips")
    j["chest"] = (chest, neck, "spine")
    j["neck"] = (neck, neck + (head_top - neck) * 0.25, "chest")
    j["head"] = (j["neck"][1], head_top, "neck")
    for i, s in enumerate("LR"):
        shoulder = p.seam(TORSO, UPPER_ARM[i])
        elbow = p.seam(UPPER_ARM[i], FOREARM[i])
        wrist = p.seam(FOREARM[i], HAND[i])
        j[f"clavicle.{s}"] = (chest.lerp(neck, 0.7), shoulder, "chest")
        j[f"upper_arm.{s}"] = (shoulder, elbow, f"clavicle.{s}")
        j[f"forearm.{s}"] = (elbow, wrist, f"upper_arm.{s}")
        knuckles = [p.seam(HAND[i], FINGERS[s][f][0]) for f in ("index", "middle", "ring",
                                                               "pinky")]
        palm = sum(knuckles, Vector()) / 4
        j[f"hand.{s}"] = (wrist, palm, f"forearm.{s}")
        for finger, (a, b, c) in FINGERS[s].items():
            base = p.seam(HAND[i], a)
            mid1, mid2 = p.seam(a, b), p.seam(b, c)
            tip = p.tip(c, mid2)
            j[f"{finger}.01.{s}"] = (base, mid1, f"hand.{s}")
            j[f"{finger}.02.{s}"] = (mid1, mid2, f"{finger}.01.{s}")
            j[f"{finger}.03.{s}"] = (mid2, tip, f"{finger}.02.{s}")
        hip = p.seam(PELVIS, THIGH[i])
        knee = p.seam(THIGH[i], SHIN[i])
        ankle = p.seam(SHIN[i], FOOT[i])
        toe = p.tip(FOOT[i], ankle)
        j[f"thigh.{s}"] = (hip, knee, "hips")
        j[f"shin.{s}"] = (knee, ankle, f"thigh.{s}")
        ball = ankle.lerp(Vector((toe.x, toe.y, 0.02)), 0.7)
        j[f"foot.{s}"] = (ankle, ball, f"shin.{s}")
        j[f"toe.{s}"] = (ball, Vector((toe.x, toe.y, 0.02)), f"foot.{s}")
    return j


def build_rig(spec: dict[str, tuple[Vector, Vector, str | None]]) -> bpy.types.Object:
    arm = bpy.data.armatures.new("human_rig")
    rig = bpy.data.objects.new("human_rig", arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, _) in spec.items():
        b = arm.edit_bones.new(name)
        b.head, b.tail = head, tail
    for name, (_, _, parent) in spec.items():
        if parent:
            arm.edit_bones[name].parent = arm.edit_bones[parent]
    # Rolls so a bone's local X is the main bending axis: across the body for the spine,
    # legs and fingers, i.e. aligned with world X at rest.
    for b in arm.edit_bones:
        b.align_roll(Vector((0.0, -1.0, 0.0)) if not b.name.startswith(("thumb",)) else
                     Vector((0.0, 0.0, 1.0)))
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "STICK"
    return rig


def hairline(p: Parts, long_back: bool = False) -> np.ndarray:
    """Per vertex, 0..1, how much is hair: the crown, above the ears, and the back down to
    the nape, each edge blended over ~1.5 cm. A per-vertex value mixed in the shader
    gives a smooth hairline; per-face materials followed the base mesh's coarse faces
    and made it a staircase."""
    head = np.zeros(len(p.co), dtype=bool)
    head[list(p.sets[HEAD])] = True
    y, z = p.co[:, 1], p.co[:, 2]
    top = z[head].max()
    ear_z = (p.centre(4).z + p.centre(5).z) / 2  # face sets 4 and 5 are the ears

    def ramp(v, width):
        return np.clip(v / width + 0.5, 0.0, 1.0)

    crown = ramp(z - (top - 0.055), 0.015)
    sides = np.minimum(ramp(y + 0.035, 0.015), ramp(z - (ear_z + 0.01), 0.015))
    # Long hair at the back reaches the nape.
    back = np.minimum(ramp(y - 0.04, 0.015), ramp(z - (ear_z - (0.12 if long_back else 0.07)),
                                                    0.02))
    return np.where(head, np.maximum.reduce([crown, sides, back]), 0.0)


def dress(obj: bpy.types.Object, p: Parts, outfit, long_back: bool = False) -> None:
    def mat(name: str, rgba) -> bpy.types.Material:
        m = bpy.data.materials.new(f"human_{name}")
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.65 if name != "skin" else 0.5
        m.diffuse_color = rgba
        return m

    obj.data.materials.clear()
    names = ["skin", "shirt", "trousers", "shoes", "hair"]
    for n, c in zip(names, (SKIN, *outfit, HAIR)):
        obj.data.materials.append(mat(n, c))
    # Skin mixes to hair by the per-vertex `hair` attribute.
    attr = obj.data.color_attributes.new("hair", "FLOAT_COLOR", "POINT")
    for i, h in enumerate(hairline(p, long_back)):
        attr.data[i].color = (h, h, h, 1.0)
    skin = obj.data.materials[0]
    nt = skin.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "hair"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = SKIN
    mix.inputs["B"].default_value = HAIR
    nt.links.new(a.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value, rough.inputs["To Max"].default_value = 0.5, 0.85
    nt.links.new(a.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])

    shirt = {TORSO, ABDOMEN, *UPPER_ARM}
    trousers = {PELVIS, *THIGH, *SHIN}
    shoes = {*FOOT} | {f for f in p.sets if p.centre(f).z < 0.05}
    for poly, f in zip(obj.data.polygons, p.face_set):
        poly.material_index = (1 if f in shirt else 2 if f in trousers else
                               3 if f in shoes else 0)


def ponytail(p: Parts) -> bpy.types.Object:
    """A ponytail from the back of the head, falling back and down, as one mesh."""
    head = p.co[np.array(list(p.sets[HEAD]))]
    ear_z = (p.centre(4).z + p.centre(5).z) / 2
    back_y = head[head[:, 2] > ear_z][:, 1].max()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16,
                                         location=(0.0, back_y + 0.016, ear_z - 0.015))
    tail = bpy.context.active_object
    tail.scale = (0.032, 0.03, 0.085)
    tail.rotation_euler.x = np.radians(-25.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    for poly in tail.data.polygons:
        poly.use_smooth = True
    # The tie, where it leaves the head.
    bpy.ops.mesh.primitive_torus_add(major_radius=0.016, minor_radius=0.006,
                                     location=(0.0, back_y + 0.002, ear_z + 0.03))
    tie = bpy.context.active_object
    tie.rotation_euler.x = np.radians(75.0)
    bpy.ops.object.select_all(action="DESELECT")
    tail.select_set(True)
    tie.select_set(True)
    bpy.context.view_layer.objects.active = tail
    bpy.ops.object.join()
    return tail


def eye_shader(mat: bpy.types.Material) -> None:
    """Sclera, a brown iris and a black pupil, from the per-vertex `iris` value."""
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.15
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "iris"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.92, 0.91, 0.88, 1.0)
    els[1].position, els[1].color = 1.0, (0.02, 0.015, 0.01, 1.0)
    for pos, col in ((0.40, (0.92, 0.91, 0.88, 1.0)), (0.45, (0.20, 0.11, 0.05, 1.0)),
                     (0.80, (0.30, 0.17, 0.08, 1.0)), (0.86, (0.02, 0.015, 0.01, 1.0))):
        e = els.new(pos)
        e.color = col
    nt.links.new(a.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    mat.diffuse_color = (0.92, 0.91, 0.88, 1.0)


def mark_irises(body: bpy.types.Object, eyes: list[range]) -> None:
    """Per eye vertex, by its angle from the eyeball's forward axis (-Y, at rest): 0 for
    the sclera, ~0.6 across the iris (28 degrees), 1 at the pupil (11 degrees)."""
    if "iris" not in body.data.color_attributes:
        body.data.color_attributes.new("iris", "FLOAT_COLOR", "POINT")
    attr = body.data.color_attributes["iris"]
    co = np.array([v.co for v in body.data.vertices])
    for r in eyes:
        idx = np.array(list(r))
        c = co[idx].mean(axis=0)
        d = co[idx] - c
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        ang = np.degrees(np.arccos(np.clip(-d[:, 1], -1.0, 1.0)))
        val = np.where(ang < 11.0, 1.0, np.where(ang < 28.0, 0.62, 0.0))
        for i, v in zip(idx, val):
            attr.data[i].color = (v, v, v, 1.0)


def attach_to_head(body: bpy.types.Object, parts: list[bpy.types.Object],
                   material: bpy.types.Material) -> range:
    """Join `parts` into the body, all in `material`, and return their vertex range, to be
    weighted fully to the head after the automatic weights. (Bone-parented objects
    drifted off the head in some poses; vertices weighted to the bone cannot.) The
    material is given as the datablock, not a slot index: a join appends the parts'
    own slots and shifts indices under anything counted before it."""
    start = len(body.data.vertices)
    for obj in parts:
        obj.data.materials.clear()
        obj.data.materials.append(material)
        for poly in obj.data.polygons:
            poly.material_index = 0
    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    return range(start, len(body.data.vertices))


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--body", choices=sorted(COLLECTIONS), default="male")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    body = append_body(args.bundle.resolve(), args.body)
    parts = Parts(body)
    spec = joints(parts)
    rig = build_rig(spec)
    dress(body, parts, OUTFITS[args.body], long_back=args.body == "female")
    eyes = [o for o in body.users_collection[0].all_objects if ".eye." in o.name]
    eye_mat = bpy.data.materials.new("human_eye")
    eye_shader(eye_mat)
    body.data.materials.append(eye_mat)
    eye_ranges = [attach_to_head(body, [eye], eye_mat) for eye in eyes]
    mark_irises(body, eye_ranges)
    head_only = [i for r in eye_ranges for i in r]
    if args.body == "female":
        head_only += list(attach_to_head(body, [ponytail(parts)],
                                         bpy.data.materials["human_hair"]))

    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    head = body.vertex_groups["head"]
    for g in body.vertex_groups:
        g.remove(head_only)
    head.add(head_only, 1.0, "REPLACE")
    used = {g.group for v in body.data.vertices for g in v.groups if g.weight > 0.0}
    empty = [g.name for g in body.vertex_groups if g.index not in used]
    print(f"rig: {len(spec)} bones; bones that got no weights: {empty or 'none'}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out.resolve()))
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()

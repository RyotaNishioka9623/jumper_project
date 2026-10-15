"""Pose the human from build_human.py: crouched in front of the crab, playing janken.

Imported by the scene scripts (Blender runs them); `crouch()` and `hand()` set a pose
on the rig at the current frame and can key it.

Bones are posed by aiming them, root to tip: each bone turns, about its own head, until
it points along a direction given in the body's frame (the body faces -Y, its left is
+X, Z up), and its children follow. Fingers are curled in the hand's own frame instead,
as local rotations taken at rest, so they keep their shape wherever the arm goes.

After posing, the rig is lowered until the lowest point of the mesh touches the floor.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

FINGERS = ("thumb", "index", "middle", "ring", "pinky")


def _update() -> None:
    bpy.context.view_layer.update()


def aim(rig: bpy.types.Object, bone: str, direction) -> None:
    """Turn `bone` about its head so it points along `direction` (armature space)."""
    pb = rig.pose.bones[bone]
    head = pb.head.copy()
    now = (pb.tail - pb.head).normalized()
    want = Vector(direction).normalized()
    rot = now.rotation_difference(want).to_matrix().to_4x4()
    pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.matrix
    _update()


def twist(rig: bpy.types.Object, bone: str, angle: float) -> None:
    """Roll `bone` about its own length by `angle` radians."""
    pb = rig.pose.bones[bone]
    axis = (pb.tail - pb.head).normalized()
    head = pb.head.copy()
    rot = Matrix.Rotation(angle, 4, axis)
    pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.matrix
    _update()


def _palm_normal(rig: bpy.types.Object, side: str) -> Vector:
    """At rest, the direction the palm of this hand faces: across the knuckles crossed
    with the hand's length, signed to point toward the body (in the A-pose the palms
    face the thighs)."""
    b = rig.data.bones
    across = b[f"index.01.{side}"].head_local - b[f"pinky.01.{side}"].head_local
    along = b[f"hand.{side}"].tail_local - b[f"hand.{side}"].head_local
    n = across.cross(along).normalized()
    inward = -1.0 if b[f"hand.{side}"].head_local.x > 0 else 1.0
    return n if n.x * inward > 0 else -n


def _curl(rig: bpy.types.Object, bone: str, palm: Vector, angle: float):
    """The local quaternion that bends `bone` toward the palm by `angle`: about the axis
    across the bone (its length crossed with the palm normal), taken at rest."""
    from mathutils import Quaternion

    b = rig.data.bones[bone]
    d = (b.tail_local - b.head_local).normalized()
    axis = d.cross(palm).normalized()
    local_axis = (b.matrix_local.to_3x3().inverted() @ axis).normalized()
    return Quaternion(local_axis, angle)


#: Per-hand-shape curl of each finger's three joints, radians; and the thumb's.
SHAPES = {
    "relaxed": {"fingers": (0.25, 0.35, 0.2), "thumb": (0.1, 0.1, 0.1)},
    "rock": {"fingers": (1.45, 1.6, 1.1), "thumb": (0.6, 0.5, 0.6)},
    "paper": {"fingers": (0.0, 0.05, 0.0), "thumb": (-0.1, 0.0, 0.0)},
}


def hand(rig: bpy.types.Object, side: str, shape: str) -> None:
    palm = _palm_normal(rig, side)
    s = SHAPES[shape]
    for finger in FINGERS:
        angles = s["thumb"] if finger == "thumb" else s["fingers"]
        for k, angle in enumerate(angles, start=1):
            name = f"{finger}.0{k}.{side}"
            pb = rig.pose.bones[name]
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = _curl(rig, name, palm, angle)
    _update()


def crouch(rig: bpy.types.Object, play: str = "L", hand_at=(0.0, 0.5, 0.26)) -> None:
    """A deep squat, leaning toward the crab, head down to it; the playing arm (`play`)
    held out with its wrist at `hand_at` -- (sideways toward its own side, forward, up
    from the floor), metres -- and the other forearm resting on its knee."""
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    _update()
    # Legs: thighs forward, knees a little apart; shins back down to the feet; feet flat.
    feet = {s: (rig.data.bones[f"foot.{s}"].tail_local - rig.data.bones[f"foot.{s}"].head_local)
            for s in "LR"}
    toes = {s: (rig.data.bones[f"toe.{s}"].tail_local - rig.data.bones[f"toe.{s}"].head_local)
            for s in "LR"}
    # Knees wide, so the playing arm reaches down between them.
    for s, x in (("L", 1.0), ("R", -1.0)):
        aim(rig, f"thigh.{s}", (0.45 * x, -0.94, 0.18))
        aim(rig, f"shin.{s}", (0.04 * x, 0.42, -0.91))
        aim(rig, f"foot.{s}", feet[s])
        aim(rig, f"toe.{s}", toes[s])
    # Bent well over toward the crab -- a crouched adult's shoulder is ~0.75 m up and the
    # arm ~0.5 m to the wrist, so only a deep lean brings the hand down to a crab's
    # height -- with the head lifted to look at it.
    aim(rig, "spine", (0.0, -0.75, 0.66))
    aim(rig, "chest", (0.0, -0.9, 0.44))
    aim(rig, "neck", (0.0, -0.85, 0.53))
    aim(rig, "head", (0.0, -0.8, 0.6))
    # The playing arm out low in front; the other resting on its knee.
    other = "L" if play == "R" else "R"
    sx = 1.0 if play == "L" else -1.0
    floor = floor_level(rig)
    side, forward, up = hand_at
    reach(rig, play, (sx * side, -forward, floor + up))
    aim(rig, f"hand.{play}", (0.1 * sx, -0.95, -0.15))
    ox = -sx
    # The other wrist on top of its knee, the hand hanging over it.
    knee = rig.pose.bones[f"shin.{other}"].head
    reach(rig, other, knee + Vector((0.0, -0.04, 0.07)), pole=(ox * 1.0, 0.2, -0.3))
    aim(rig, f"hand.{other}", (-0.2 * ox, -0.6, -0.8))
    hand(rig, other, "relaxed")


def floor_level(rig: bpy.types.Object) -> float:
    """Armature-space height of the floor under the posed feet (the toes' lowest end)."""
    _update()
    return min(min(rig.pose.bones[f"toe.{s}"].tail.z, rig.pose.bones[f"foot.{s}"].head.z - 0.07)
               for s in "LR")


def reach(rig: bpy.types.Object, side: str, target, pole=None) -> None:
    """Put the wrist of `side` at `target` (armature space) with the elbow bent toward
    `pole`: two-bone IK, solved once, then posed by aiming the upper arm and forearm."""
    sx = 1.0 if side == "L" else -1.0
    pole = Vector(pole or (sx * 1.0, 0.3, -0.6)).normalized()
    upper, fore = rig.pose.bones[f"upper_arm.{side}"], rig.pose.bones[f"forearm.{side}"]
    l1, l2 = upper.length, fore.length
    s0 = upper.head.copy()
    t = Vector(target)
    d = t - s0
    dist = min(d.length, (l1 + l2) * 0.999)
    dn = d.normalized()
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2.0 * dist)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    perp = (pole - dn * pole.dot(dn)).normalized()
    elbow = s0 + dn * a + perp * h
    aim(rig, f"upper_arm.{side}", elbow - s0)
    aim(rig, f"forearm.{side}", s0 + dn * dist - elbow)


def grounded(rig: bpy.types.Object, body: bpy.types.Object) -> None:
    """Move the rig so the posed mesh's lowest point sits on the floor (z = 0)."""
    _update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(deps)
    mw = ev.matrix_world
    low = min((mw @ v.co).z for v in ev.data.vertices)
    rig.location.z -= low
    _update()


def place(rig: bpy.types.Object, x: float, y: float, facing_deg: float) -> None:
    """Stand the rig at (x, y) turned so it faces `facing_deg` (0 = +X, 180 = -X)."""
    rig.location.x, rig.location.y = x, y
    # The body faces -Y, i.e. -90 degrees; turn it to `facing_deg`.
    rig.rotation_euler = (0.0, 0.0, math.radians(facing_deg + 90.0))
    _update()

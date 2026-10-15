"""Stage a janken take: the set, the crab's recorded motion and face, and the human.

    blender scissors_crab/renders/sets/home_set.blend --background \
        --python scissors_crab/blender/stage.py -- \
        scissors_crab/renders/janken_lose/1fb58d6/rollout.npz \
        --eyes scissors_crab/renders/janken_lose/1fb58d6/eyes \
        --human scissors_crab/renders/sets/human_male.blend --throw rock \
        --render take.mp4

The base .blend is the rig on a set (import_scene.py). The crab's motion and eyes are
put on as import_motion.py does. The human (build_human.py) is appended, crouched in
front of the crab facing it, and keyed through the game in step with the crab's
opening: half crouched with its hands on its knees, peering at the crab while it
practises; a fist raised as the crab readies, two swings on "jan" and "ken", and on
"pon" a dip and the hand thrown -- `--throw rock` against the losing take, `paper`
against the winning one. The crab's opening is shared, so the frames below hold for
every take.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_motion as im
import pose_human as ph

#: The crab's opening, in render frames: keyframe frames (janken_common.py) plus the
#: converter's 0.4 s lead-in (12 frames at 30 fps).
LEAD = 12
READY, JAN, JAN_UP, KEN, KEN_UP, PON = (f + LEAD for f in (76, 84, 90, 96, 102, 108))

#: Where the human stands, facing the crab (-X); and for each beat of the game, how deep
#: it bends (pose_human.half_crouch) and where its playing hand goes, relative to its
#: own feet: (toward its playing side, forward, up from the floor).
HUMAN_AT = (0.8, 0.0)
UP, DOWN, THROW = ((0.35, (0.08, 0.42, 0.62)), (0.45, (0.08, 0.46, 0.52)),
                   (1.3, (0.08, 0.55, 0.32)))


def light_set() -> None:
    """Afternoon in the living room: warm sun slanting in through the window behind the
    sofa (+Y), a soft cool fill from the room side, and a pale sky for ambient light.
    Replaces the rig's single grey studio sun."""
    import math

    old = bpy.data.objects.get("sun")
    if old is not None:
        bpy.data.objects.remove(old)
    scene = bpy.context.scene

    def light(name, kind, energy, colour, rot=None, loc=None, size=None):
        data = bpy.data.lights.new(name, kind)
        data.energy, data.color = energy, colour
        if size is not None:
            if kind == "SUN":
                data.angle = size
            else:
                data.size = size
        obj = bpy.data.objects.new(name, data)
        if rot:
            obj.rotation_euler = tuple(math.radians(a) for a in rot)
        if loc:
            obj.location = loc
        scene.collection.objects.link(obj)
        return obj

    # Through the window: from +Y, 35 degrees up, a touch from the side.
    light("window_sun", "SUN", 2.2, (1.0, 0.9, 0.76), rot=(-55.0, 0.0, 200.0), size=0.08)
    # Fill from the room, large and soft, slightly cool.
    fill = light("room_fill", "AREA", 35.0, (0.86, 0.9, 1.0), loc=(1.6, -1.6, 1.6), size=1.5)
    fill.rotation_euler = (math.radians(55.0), 0.0, math.radians(45.0))
    if scene.world is None:
        scene.world = bpy.data.worlds.new("world")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.78, 0.82, 0.88, 1.0)
    bg.inputs["Strength"].default_value = 0.3
    # Standard keeps the crab's red red; AgX washed it toward salmon.
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    eevee = scene.eevee
    for attr, value in (("use_raytracing", True), ("use_shadows", True)):
        if hasattr(eevee, attr):
            setattr(eevee, attr, value)


def append_human(path: Path) -> tuple[bpy.types.Object, bpy.types.Object]:
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c.startswith("Body ")]
        dst.objects = ["human_rig"]
    for c in dst.collections:
        bpy.context.scene.collection.children.link(c)
    rig = bpy.data.objects["human_rig"]
    bpy.context.scene.collection.objects.link(rig)
    body = next(o for o in dst.collections[0].all_objects
                if o.type == "MESH" and ".eye." not in o.name)
    return rig, body


def clear_floor(points: list[tuple[float, float]], radius: float) -> list[str]:
    """Hide the set's pieces standing within `radius` of any of `points` (x, y): props
    the performers would stand in. Returns their names."""
    from mathutils import Vector

    hidden = []
    scene = bpy.data.collections.get("scene")
    for obj in (scene.objects if scene else []):
        if obj.type != "MESH" or obj.dimensions.x > 1.0 or obj.dimensions.y > 1.0:
            continue  # floors, walls and furniture stay
        c = obj.matrix_world @ (sum((Vector(b) for b in obj.bound_box), Vector()) / 8)
        if any((c.x - x) ** 2 + (c.y - y) ** 2 < radius ** 2 for x, y in points):
            obj.hide_render = obj.hide_viewport = True
            hidden.append(obj.name)
    return hidden


def key_pose(rig: bpy.types.Object, frame: int) -> None:
    for pb in rig.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=frame)


def human_take(rig: bpy.types.Object, body: bpy.types.Object, throw: str) -> None:
    ph.place(rig, *HUMAN_AT, facing_deg=180.0)

    def pose(frame: int, beat=None, shape: str = "rock") -> None:
        if beat is None:
            ph.half_crouch(rig)  # hands on knees, peering
        else:
            bend, hand_at = beat
            ph.half_crouch(rig, bend=bend, play="L", hand_at=hand_at, shape=shape)
        # Each pose bends the legs differently: set the feet on the floor per key.
        rig.location.z = 0.0
        ph.grounded(rig, body)
        key_pose(rig, frame)
        rig.keyframe_insert("location", index=2, frame=frame)

    pose(1)
    pose(READY - 10)
    pose(READY, UP)
    pose(JAN, DOWN)
    pose(JAN_UP, UP)
    pose(KEN, DOWN)
    pose(KEN_UP, UP)
    pose(PON, THROW, throw)
    pose(PON + 200, THROW, throw)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("motion", type=Path)
    ap.add_argument("--eyes", type=Path)
    ap.add_argument("--human", type=Path, required=True, help="build_human.py's .blend")
    ap.add_argument("--throw", choices=("rock", "paper"), required=True)
    ap.add_argument("--save", type=Path)
    ap.add_argument("--render", type=Path)
    ap.add_argument("--frames", type=int, nargs=2, metavar=("FIRST", "LAST"))
    ap.add_argument("--size", type=int, nargs=2, default=(1280, 720), metavar=("W", "H"))
    # Over the human's left shoulder, low: the crab's face to camera, the human's arm and
    # knee framing it, the human's face out of shot (a still, realistic face reads as
    # uncanny).
    ap.add_argument("--camera", type=float, nargs=3, default=(0.85, -0.75, 0.85))
    ap.add_argument("--look-at", type=float, nargs=3, default=(0.05, -0.04, 0.14))
    ap.add_argument("--lens", type=float, default=40.0, help="focal length, mm")
    args = ap.parse_args(argv)

    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    dt, base, joints, names = im.read_motion(args.motion.resolve())
    n = im.key_motion(im.resample(dt, base, fps), im.resample(dt, joints, fps), names)
    scene.frame_start, scene.frame_end = 1, n
    if args.eyes:
        im.set_eyes(args.eyes.resolve(), n)
    light_set()
    rig, body = append_human(args.human.resolve())
    human_take(rig, body, args.throw)
    hidden = clear_floor([(0.0, 0.0), HUMAN_AT, (HUMAN_AT[0] - 0.4, HUMAN_AT[1])], 0.45)
    if hidden:
        print(f"cleared from the floor: {', '.join(hidden)}")
    bpy.data.objects["cam"].location = args.camera
    bpy.data.objects["cam"].data.lens = args.lens
    bpy.data.objects["cam_target"].location = args.look_at
    print(f"staged {n} frames: crab from {args.motion.name}, human throws {args.throw}")
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=str(args.save.resolve()))
    if args.render:
        if args.frames:
            scene.frame_start, scene.frame_end = args.frames
        im.render(args.render.resolve(), tuple(args.size))


if __name__ == "__main__":
    main()

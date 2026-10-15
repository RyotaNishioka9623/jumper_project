"""The last shot: from the crab that just won, across the room, to two crabs drawing forever.

    blender scissors_crab/renders/sets/home_set.blend --background \
        --python scissors_crab/blender/ending.py -- \
        --win scissors_crab/renders/janken_win/441c908/rollout.npz \
        --win-eyes scissors_crab/renders/janken_win/441c908/eyes \
        --draw scissors_crab/renders/janken_draw/97f28f8/rollout.npz \
        --draw-eyes scissors_crab/renders/janken_draw/97f28f8/eyes \
        --human scissors_crab/renders/sets/human_female.blend \
        --render scissors_crab/renders/ending/ending.mp4 --frames 190 480

One set, one continuous camera. The winning take plays where stage.py puts it -- the
crab at the origin, the human throwing paper over its shoulder -- while behind them,
in front of the bed, a second rig and its mirrored twin play the draw's "aiko de sho"
cycle over and over: the cycle starts and ends on the scissors pose (36 frames;
the replay's seam is under a degree), so it is tiled for as long as the shot runs. The
camera holds on the shy winner over the human's shoulder, then travels across the room
and settles on the pair, side on. The fade-out is the edit's (edit.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_motion as im
import stage

REPO = Path(__file__).resolve().parents[2]
RIG = REPO / "scissors_crab" / "blender" / "jumper_rig.blend"

#: The draw's cycle in render frames (keyframe frames + the 12-frame lead-in): the
#: first "aiko de sho" starts at 126 + 12 and each runs 36 frames.
CYCLE = (138, 174)
#: Where the drawing pair stands: the first crab here facing +X, its twin `GAP` ahead.
PAIR_AT = (-1.35, -0.75)
GAP = 0.6
#: Camera: (frame, position, look-at). Over the human's shoulder on the winner, then an
#: arc across the room to the pair, side on.
CAMERA = (
    (1, (0.85, -0.75, 0.85), (0.05, -0.04, 0.14)),
    (230, (0.85, -0.75, 0.85), (0.05, -0.04, 0.14)),
    (268, (0.1, -1.75, 0.95), (-0.6, -0.5, 0.16)),
    (305, (-1.05, -2.05, 0.6), (-1.05, -0.75, 0.13)),
)


def append_rig() -> bpy.types.Collection:
    """A second crab rig from build_rig.py's file, in its own collection."""
    before = set(bpy.data.collections)
    with bpy.data.libraries.load(str(RIG), link=False) as (_, dst):
        dst.collections = ["jumper_rig"]
    coll = next(c for c in dst.collections if c not in before)
    bpy.context.scene.collection.children.link(coll)
    return coll


def tiled(dt: float, data: np.ndarray, fps: float, frames: int) -> np.ndarray:
    """The rollout up to the end of the cycle, then the cycle again and again."""
    x = im.resample(dt, data, fps)
    a, b = CYCLE[0] - 1, CYCLE[1] - 1
    out = list(x[:b])
    while len(out) < frames:
        out.extend(x[a:b])
    return np.array(out[:frames])


def key_camera() -> None:
    cam, target = bpy.data.objects["cam"], bpy.data.objects["cam_target"]
    for frame, pos, look in CAMERA:
        cam.location, target.location = pos, look
        cam.keyframe_insert("location", frame=frame)
        target.keyframe_insert("location", frame=frame)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", type=Path, required=True)
    ap.add_argument("--win-eyes", type=Path, required=True)
    ap.add_argument("--draw", type=Path, required=True)
    ap.add_argument("--draw-eyes", type=Path, required=True)
    ap.add_argument("--human", type=Path, required=True)
    ap.add_argument("--length", type=int, default=480, help="frames in the shot")
    ap.add_argument("--frames", type=int, nargs=2, metavar=("FIRST", "LAST"))
    ap.add_argument("--size", type=int, nargs=2, default=(1280, 720), metavar=("W", "H"))
    ap.add_argument("--save", type=Path)
    ap.add_argument("--render", type=Path)
    args = ap.parse_args(argv)

    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base

    # The winner, where stage.py puts it.
    dt, base, joints, names = im.read_motion(args.win.resolve())
    n = im.key_motion(im.resample(dt, base, fps), im.resample(dt, joints, fps), names)
    im.set_eyes(args.win_eyes.resolve(), n)

    # The pair, drawing forever.
    pair = append_rig()
    anchor = bpy.data.objects.new("pair_anchor", None)
    anchor.location = (*PAIR_AT, 0.0)
    pair.objects.link(anchor)
    root, _ = im.rig_objects(pair)
    root.parent = anchor
    dt, base, joints, names = im.read_motion(args.draw.resolve())
    im.key_motion(tiled(dt, base, fps, args.length), tiled(dt, joints, fps, args.length),
                  names, coll=pair)
    im.set_eyes(args.draw_eyes.resolve(), args.length, coll=pair)
    im.add_twin(GAP, coll=pair, at_x=PAIR_AT[0])
    floor = bpy.data.objects.get("floor.001")
    if floor is not None:  # the appended rig's own studio floor
        floor.hide_render = floor.hide_viewport = True

    stage.light_set()
    rig, body = stage.append_human(args.human.resolve())
    stage.human_take(rig, body, "paper")
    stage.clear_floor([(0.0, 0.0), stage.HUMAN_AT, (stage.HUMAN_AT[0] - 0.4, 0.0),
                       PAIR_AT, (PAIR_AT[0] + GAP, PAIR_AT[1])], 0.45)
    key_camera()
    bpy.data.objects["cam"].data.lens = 40.0
    scene.frame_start, scene.frame_end = 1, args.length
    print(f"ending: winner from {args.win.name}, pair from {args.draw.name}, "
          f"{args.length} frames")
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=str(args.save.resolve()))
    if args.render:
        if args.frames:
            scene.frame_start, scene.frame_end = args.frames
        im.render(args.render.resolve(), tuple(args.size))


if __name__ == "__main__":
    main()

"""Put a recorded motion and an eye timeline on the Jumper rig, and optionally render it.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/blender/import_motion.py -- \
        rollout.npz --eyes scissors_crab/renders/janken_lose/eyes \
        --save scissors_crab/renders/janken_lose/scene.blend \
        --render scissors_crab/renders/janken_lose/janken_lose.mp4

Two kinds of motion are read:

- a replay, written by `scripts/play.py --qpos-out`: what a trained policy did in
  the simulator, base included. This is the one the videos are made from.
- a clip, a task's `media/*.npz`: the reference itself (`meas_body_*`, `meas_L*_j*`),
  to look at a choreography in Blender before anything is trained.

The motion is resampled to the scene's frame rate and keyed on `jumper_root` (the
floating base, as a quaternion) and the 22 joints. `--eyes` points at the directory
`make_eyes.py` writes, whose `R/` and `L/` image sequences become the two displays.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Quaternion

#: The clip schema's leg order (`tasks/jumper/common/dance/motion.py`, LEG_JOINTS):
#: source leg k, joint j is channel `L{k}_j{j}`.
LEG_ORDER = ("LF", "LM", "LR", "RR", "RM", "RF")
ARM = {"LF", "RF"}


def read_motion(path: Path) -> tuple[float, np.ndarray, np.ndarray, list[str]]:
    """(dt, base [T, 7] xyz + wxyz, joints [T, J], joint names)."""
    with np.load(path) as z:
        if "qpos" in z:
            qpos = z["qpos"].astype(np.float64)
            names = [str(n) for n in z["joint_names"]]
            types, adr = z["joint_type"], z["joint_qposadr"]
            free = [i for i, t in enumerate(types) if t == 0]
            if len(free) != 1:
                raise ValueError(f"{path}: expected one floating base, found {len(free)}")
            b = int(adr[free[0]])
            hinges = [i for i, t in enumerate(types) if t == 3]
            joint_names = [names[i].rsplit("/", 1)[-1] for i in hinges]
            joints = qpos[:, [int(adr[i]) for i in hinges]]
            return float(z["dt"]), qpos[:, b:b + 7], joints, joint_names
        if "meas_body_x" in z:
            base_xyz = np.stack([z[f"meas_body_{a}"] for a in "xyz"], axis=1)
            rpy = np.stack([z[f"meas_body_{a}"] for a in ("roll", "pitch", "yaw")], axis=1)
            # R = Rz(yaw) Ry(pitch) Rx(roll), the clip's convention; Blender's XYZ Euler.
            quat = np.array([list(Euler(r, "XYZ").to_quaternion()) for r in rpy])
            joint_names, cols = [], []
            for k, leg in enumerate(LEG_ORDER):
                for j in range(5 if leg in ARM else 3):
                    joint_names.append(f"{leg}_J{j}_joint")
                    cols.append(z[f"meas_L{k}_j{j}"])
            return (float(z["dt"]), np.concatenate([base_xyz, quat], axis=1).astype(np.float64),
                    np.stack(cols, axis=1).astype(np.float64), joint_names)
    raise ValueError(f"{path}: neither a replay (qpos) nor a clip (meas_*)")


def resample(dt: float, data: np.ndarray, fps: float) -> np.ndarray:
    t_src = np.arange(len(data)) * dt
    t_dst = np.arange(0.0, t_src[-1] + 1e-9, 1.0 / fps)
    return np.stack([np.interp(t_dst, t_src, data[:, c]) for c in range(data.shape[1])], axis=1)


def key_motion(base: np.ndarray, joints: np.ndarray, names: list[str]) -> int:
    rig = {o["joint"]: o for o in bpy.data.objects if "joint" in o}
    missing = set(rig) - set(names)
    if missing:
        raise ValueError(f"the motion has no {sorted(missing)}")
    root = bpy.data.objects["jumper_root"]
    for obj in [root, *rig.values()]:
        obj.animation_data_clear()
    root.rotation_mode = "QUATERNION"
    prev = None
    for f, row in enumerate(base, start=1):
        q = Quaternion(row[3:7]).normalized()
        if prev is not None and prev.dot(q) < 0.0:
            q.negate()  # keep the quaternion track continuous
        prev = q
        root.location = row[:3]
        root.rotation_quaternion = q
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_quaternion", frame=f)
    for c, name in enumerate(names):
        obj = rig.get(name)
        if obj is None:
            continue
        i = obj["axis"]
        for f, v in enumerate(joints[:, c], start=1):
            obj.rotation_euler[i] = v
            obj.keyframe_insert("rotation_euler", index=i, frame=f)
    return len(base)


def set_eyes(eyes: Path, frames: int) -> None:
    for side in ("R", "L"):
        seq = sorted((eyes / side).glob("*.png"))
        if not seq:
            raise ValueError(f"{eyes / side} has no frames; run make_eyes.py")
        node = bpy.data.materials[f"eye_{side}"].node_tree.nodes["eye_image"]
        img = bpy.data.images.load(str(seq[0].resolve()))
        img.source = "SEQUENCE"
        node.image = img
        node.image_user.frame_start = 1
        node.image_user.frame_offset = 0
        node.image_user.frame_duration = max(frames, len(seq))
        node.image_user.use_auto_refresh = True
        if len(seq) < frames:
            print(f"warning: {side} eye has {len(seq)} frames for a {frames}-frame motion; "
                  "it holds its last frame")


def render(out: Path, size: tuple[int, int]) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    tmp = Path(tempfile.mkdtemp(prefix="jumper_render_"))
    try:
        scene.render.filepath = str(tmp / "f_")
        bpy.ops.render.render(animation=True)
        fps = scene.render.fps / scene.render.fps_base
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-framerate", f"{fps:g}",
             "-start_number", str(scene.frame_start), "-i", str(tmp / "f_%04d.png"),
             "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "18", str(out)],
            check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"rendered {scene.frame_end - scene.frame_start + 1} frames -> {out}")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("motion", type=Path, help="a play.py --qpos-out replay, or a task clip")
    ap.add_argument("--eyes", type=Path, help="make_eyes.py's output directory")
    ap.add_argument("--save", type=Path, help="save the scene as this .blend")
    ap.add_argument("--render", type=Path, help="render the animation to this .mp4")
    ap.add_argument("--size", type=int, nargs=2, default=(1280, 720), metavar=("W", "H"))
    ap.add_argument("--camera", type=float, nargs=3, metavar=("X", "Y", "Z"),
                    default=(0.62, -0.38, 0.30), help="camera position, metres")
    ap.add_argument("--look-at", type=float, nargs=3, metavar=("X", "Y", "Z"),
                    default=(0.04, -0.02, 0.10))
    args = ap.parse_args(argv)

    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    dt, base, joints, names = read_motion(args.motion.resolve())
    n = key_motion(resample(dt, base, fps), resample(dt, joints, fps), names)
    scene.frame_start, scene.frame_end = 1, n
    print(f"keyed {n} frames ({(n - 1) / fps:.2f} s) from {args.motion.name}")
    if args.eyes:
        set_eyes(args.eyes.resolve(), n)
    bpy.data.objects["cam"].location = args.camera
    bpy.data.objects["cam_target"].location = args.look_at
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.save.resolve()))
        print(f"saved {args.save}")
    if args.render:
        render(args.render.resolve(), tuple(args.size))


if __name__ == "__main__":
    main()

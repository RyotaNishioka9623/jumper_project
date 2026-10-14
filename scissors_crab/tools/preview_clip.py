#!/usr/bin/env python3
"""Render a gesture clip as it is written, before any policy is trained on it.

    python scissors_crab/tools/preview_clip.py tasks/jumper/janken_lose/media/janken_lose.npz \
        --out preview.mp4

The clip's own base pose (`meas_body_*`, solved by `keyframes_to_npz.py`) and joint
angles are written straight into `qpos` frame by frame: kinematic playback, no
physics. It shows what the policy will be asked to imitate -- whether the feet stay
on the floor, how the body tilts -- which a Blender viewport with a fixed base cannot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def build_model():
    import mujoco

    spec = mujoco.MjSpec.from_file(str(REPO / "assets" / "jumper" / "jumper.xml"))
    tex = spec.add_texture(name="grid", type=mujoco.mjtTexture.mjTEXTURE_2D,
                           builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                           rgb1=[0.82, 0.82, 0.80], rgb2=[0.74, 0.74, 0.72],
                           width=512, height=512)
    mat = spec.add_material(name="grid", texrepeat=[8, 8], reflectance=0.05)
    mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = tex.name
    spec.worldbody.add_geom(type=mujoco.mjtGeom.mjGEOM_PLANE, size=[2, 2, 0.1],
                            material="grid")
    # A key from the front-right and a softer fill from the left, both directional,
    # over a bright headlight, so the dark underside still reads.
    directional = mujoco.mjtLightType.mjLIGHT_DIRECTIONAL
    spec.worldbody.add_light(type=directional, pos=[2, -2, 3], dir=[-0.5, 0.5, -1],
                             diffuse=[0.7] * 3, castshadow=True)
    spec.worldbody.add_light(type=directional, pos=[-2, 2, 2], dir=[0.5, -0.5, -1],
                             diffuse=[0.3] * 3, castshadow=False)
    spec.visual.headlight.ambient = [0.35] * 3
    spec.visual.headlight.diffuse = [0.35] * 3
    spec.visual.rgba.haze = [0.9, 0.9, 0.9, 1]
    return spec.compile()


def main(argv: list[str] | None = None) -> int:
    import mediapy
    import mujoco

    from tasks.jumper.common.dance.motion import LEG_JOINTS, _rpy_to_quat

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("clip", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", type=int, nargs=2, default=(960, 720), metavar=("W", "H"))
    ap.add_argument("--azimuth", type=float, default=150.0,
                    help="degrees; 180 faces the robot head-on, 90 is from its right side")
    ap.add_argument("--elevation", type=float, default=-18.0)
    ap.add_argument("--distance", type=float, default=0.75)
    args = ap.parse_args(argv)

    model = build_model()
    data = mujoco.MjData(model)
    with np.load(args.clip) as z:
        dt = float(z["dt"])
        base = np.stack([z[f"meas_body_{a}"] for a in ("x", "y", "z", "roll", "pitch", "yaw")],
                        axis=1).astype(np.float64)
        names, cols = [], []
        for leg in sorted(LEG_JOINTS):
            for j, name in enumerate(LEG_JOINTS[leg]):
                names.append(name)
                cols.append(np.asarray(z[f"meas_L{leg}_j{j}"], dtype=np.float64))
        q = np.stack(cols, axis=1)
    adr = [model.jnt_qposadr[model.joint(n).id] for n in names]

    renderer = mujoco.Renderer(model, height=args.size[1], width=args.size[0])
    cam = mujoco.MjvCamera()
    cam.azimuth, cam.elevation, cam.distance = args.azimuth, args.elevation, args.distance
    # The clip's convention, R = Rz(yaw) Ry(pitch) Rx(roll), as the trainer reads it.
    quat = _rpy_to_quat(base[:, 3:6])
    frames = []
    t_end = (len(q) - 1) * dt
    for t in np.arange(0.0, t_end + 1e-9, 1.0 / args.fps):
        k = min(round(t / dt), len(q) - 1)
        data.qpos[:3] = base[k, :3]
        data.qpos[3:7] = quat[k]
        data.qpos[adr] = q[k]
        mujoco.mj_kinematics(model, data)
        cam.lookat[:] = [base[k, 0], base[k, 1], 0.06]
        renderer.update_scene(data, camera=cam)
        frames.append(renderer.render())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    mediapy.write_video(str(args.out), frames, fps=args.fps)
    print(f"{args.clip.name}: {len(frames)} frames ({t_end:.2f} s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Export the joint angles animated on the Jumper rig as a keyframe table.

In Blender (Scripting tab, open this file, Run Script), with the rig built by
`build_rig.py` open; the table goes next to the .blend as `<blend name>.keyframes.json`.

From the command line:

    blender scissors_crab/motions/janken.blend --background \
        --python scissors_crab/blender/export_keyframes.py -- --out janken.keyframes.json

The scene's frame range is sampled at `RATE_HZ`, subframes included, so the table
follows the F-curves' interpolation rather than only the keys. Joint angles are
written, and `lift` when `jumper_root` is raised above its rest height somewhere (a
jump); the rest of the base pose is solved from the joints by `keyframes_to_npz.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

RATE_HZ = 100
FORMAT = "scissors-crab-keyframes/1"


def joints() -> list[bpy.types.Object]:
    found = [o for o in bpy.data.objects if "joint" in o]
    if len(found) != 22:
        raise RuntimeError(f"expected the 22 joints of build_rig.py's rig, found {len(found)}")
    return sorted(found, key=lambda o: o["joint"])


def sample(objs: list[bpy.types.Object]
           ) -> tuple[list[list[float]], list[float], float, dict[str, float]]:
    """Rows of joint angles, the root's lift per row, the scene's fps, and how far each
    clamped joint went past its range.

    The angle is read from `rotation_euler`, not from the world matrix: the shoulders'
    J1 range is -4.75..1.4 rad, past half a turn, and a matrix would fold it back.
    It is clamped to the joint range here, which is what the viewport's Limit Rotation
    shows for the joints that have one."""
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    start, end = scene.frame_start, scene.frame_end
    n = round((end - start) / fps * RATE_HZ) + 1
    root = bpy.data.objects["jumper_root"]
    rows, lift, over = [], [], {}
    for k in range(n):
        f = start + k * fps / RATE_HZ
        scene.frame_set(int(f), subframe=f - int(f))
        row = []
        for o in objs:
            lo, hi = o["range"]
            v = o.rotation_euler[o["axis"]]
            if not lo <= v <= hi:
                over[o["joint"]] = max(over.get(o["joint"], 0.0), lo - v, v - hi)
            row.append(min(max(v, lo), hi))
        rows.append(row)
        lift.append(max(0.0, root.location.z - root.get("rest_z", root.location.z)))
    return rows, lift, fps, over


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    blend = Path(bpy.data.filepath) if bpy.data.filepath else None
    out = args.out or (blend.with_suffix(".keyframes.json") if blend else None)
    if out is None:
        raise RuntimeError("save the .blend first, or pass --out")

    objs = joints()
    rows, lift, fps, over = sample(objs)
    for name, by in sorted(over.items()):
        print(f"warning: {name} animated up to {by:.3f} rad past its range; clamped")
    table = {
        "format": FORMAT,
        "name": blend.stem if blend else out.stem,
        "rate_hz": RATE_HZ,
        "joint_order": [o["joint"] for o in objs],
        "q": [[round(v, 6) for v in r] for r in rows],
        "blend": blend.name if blend else None,
        "fps": fps,
        "frames": [bpy.context.scene.frame_start, bpy.context.scene.frame_end],
        "blender": bpy.app.version_string,
    }
    # The root's location is single precision; below 0.1 mm it has not been raised.
    if max(lift) > 1e-4:
        table["lift"] = [round(v, 6) for v in lift]
        print(f"jump: the root rises up to {max(lift) * 1000:.0f} mm")
    out = Path(out).resolve()
    out.write_text(json.dumps(table))
    print(f"exported {len(rows)} rows ({(len(rows) - 1) / RATE_HZ:.2f} s) of "
          f"{len(objs)} joints -> {out}")


if __name__ == "__main__":
    main()

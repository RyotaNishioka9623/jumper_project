#!/usr/bin/env python3
"""Turn a keyframe table exported from Blender into a gesture task's choreography.

    python scissors_crab/tools/keyframes_to_npz.py \
        scissors_crab/motions/janken_lose.keyframes.json --task janken_lose

The table is joint angles only (`scissors_crab/blender/export_keyframes.py`). What
makes it a clip the trainer can imitate is done exactly as for the official gestures
(`tools/import_wbc_gestures.py`), whose `paw` was also made from hand-placed
keyframes, by reusing that tool's functions:

- joints clamped to the MJCF ranges,
- a smoothstep lead-in from `HOME` and lead-out back to it, then `HOLD_S` at `HOME`,
- the base pose solved from the joints: the floor is the plane the robot rests on
  through three of its six feet, and planted feet are held from row to row.

The base pose is quasi-static by construction: the robot rests on the floor. A jump is
the one exception, and it is keyframed rather than solved: the table's optional `lift`
(metres, how far `jumper_root` was raised in Blender) is added to the solved height,
so through a hop the feet leave the floor by exactly that much. Shape it as physics
would -- a parabola under g through the flight, a fast leg extension into it -- or the
policy is scored against a hop it cannot make.

The clip is written to `tasks/jumper/<task>/media/<name>.npz`, with the source
table's sha256 for provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "tools")]

import import_wbc_dances as dances
import import_wbc_gestures as gestures

FORMAT = "scissors-crab-keyframes/1"


def read_table(path: Path, names: list[str]) -> tuple[np.ndarray, np.ndarray, float, bytes]:
    """(joints [T, 22] in the robot's channel order, lift [T] in metres, dt, the raw file)."""
    raw = path.read_bytes()
    d = json.loads(raw)
    if d.get("format") != FORMAT:
        raise ValueError(f"{path}: format is {d.get('format')!r}, expected {FORMAT!r}")
    order = d["joint_order"]
    if sorted(order) != sorted(names):
        raise ValueError(f"{path}: joint_order is not the robot's 22 joints")
    q = np.asarray(d["q"], dtype=np.float64)[:, [order.index(n) for n in names]]
    lift = np.asarray(d.get("lift", np.zeros(len(q))), dtype=np.float64)
    if lift.shape != (len(q),) or lift.min() < 0.0:
        raise ValueError(f"{path}: lift must be one non-negative value per row")
    return q, lift, 1.0 / float(d["rate_hz"]), raw


#: Fastest the solved body may tilt, deg/s. The resting-floor solver puts the robot on
#: whichever three feet it would rest on, and when a joint path changes that choice --
#: a claw coming down below the legs, the centre of mass passing over an edge -- it
#: changes in one row: the body tips in one step. A real robot rocks over in a moment,
#: not in no time, and a step is a reference no policy can follow; at the end of the
#: first janken_win it tipped 15 degrees and back and looked like a hop of the rear.
#: Keyframed motion here tilts at most ~60 deg/s; a snap is hundreds.
SNAP_DEG_S = 150.0
#: Half the window a snap is eased over, seconds: the rock takes 0.3 s.
SNAP_EASE_S = 0.15


def snaps(pose: np.ndarray, dt: float) -> list[tuple[float, float]]:
    """(time, deg/s) of each place the body's roll or pitch jumps faster than SNAP_DEG_S."""
    rate = np.degrees(np.abs(np.diff(pose[:, 3:5], axis=0))).max(axis=1) / dt
    fast = np.nonzero(rate > SNAP_DEG_S)[0]
    # One report per snap, at its fastest row.
    out: list[tuple[float, float]] = []
    for i in fast:
        if out and i * dt - out[-1][0] < 0.1:
            if rate[i] > out[-1][1]:
                out[-1] = (i * dt, float(rate[i]))
            continue
        out.append((i * dt, float(rate[i])))
    return out


def ease_snaps(pose: np.ndarray, dt: float) -> int:
    """Replace the height, roll and pitch around each snap with a smoothstep from the
    window's first row to its last, in place. x, y and yaw are left alone. Returns how
    many snaps were eased; key a path that sets the robot down rather than leaning on
    this for anything large."""
    w = round(SNAP_EASE_S / dt)
    eased = 0
    for _ in range(3):
        found = snaps(pose, dt)
        if not found:
            break
        for when, _rate in found:
            i = round(when / dt)
            a, b = max(0, i - w), min(len(pose) - 1, i + w + 1)
            u = np.arange(b - a + 1) / (b - a)
            u = (u * u * (3.0 - 2.0 * u))[:, None]
            pose[a:b + 1, 2:5] = pose[a, 2:5] + (pose[b, 2:5] - pose[a, 2:5]) * u
            eased += 1
    return eased


def convert(path: Path, task: str, name: str | None) -> Path:
    from tasks.jumper.common.constants import HOME

    robot = gestures._Robot()
    q, lift, dt, raw = read_table(path, robot.names)
    name = name or json.loads(raw)["name"]

    lo, hi = robot.range[:, 0], robot.range[:, 1]
    over = np.maximum(lo - q.min(axis=0), q.max(axis=0) - hi)
    clamped = [(robot.names[i], over[i]) for i in np.nonzero(over > 0.0)[0]]
    q = np.clip(q, lo, hi)

    home = np.array([HOME[n] for n in robot.names])
    lead_in, t_in = gestures._lead(home, q[0], dt)
    lead_out, t_out = gestures._lead(q[-1], home, dt)
    hold = np.repeat(home[None], round(gestures.HOLD_S / dt) + 1, axis=0)
    q = np.concatenate([lead_in, q, lead_out, hold])
    lift = np.concatenate([np.zeros(len(lead_in)), lift,
                           np.zeros(len(lead_out) + len(hold))])

    pose, height = gestures.solve_resting_pose(robot, q)
    found = snaps(pose, dt)
    eased = ease_snaps(pose, dt)
    pose[:, 2] += lift
    height += lift[:, None]
    lifted = {f: float((height[:, i] >= gestures.DOWN_TOL).mean())
              for i, f in enumerate(gestures.FEET)}

    n = len(q)
    f32 = np.float32
    out: dict[str, np.ndarray] = {
        "time": (np.arange(n) * dt).astype(f32),
        "dt": np.array(dt),
        "phase": np.ones(n, dtype=f32),
    }
    for prefix in ("", "meas_"):
        for i, a in enumerate(dances.AXES):
            out[f"{prefix}body_{a}"] = pose[:, i].astype(f32)
        for k, key in enumerate(dances._keys()):
            out[f"{prefix}{key}"] = q[:, k].astype(f32)
    out["source"] = np.array(f"scissors_crab:{path.name}")
    out["source_sha256"] = np.array(hashlib.sha256(raw).hexdigest())
    out["lead_in_s"] = np.array(t_in)
    out["lead_out_s"] = np.array(t_out)
    out["hold_s"] = np.array(gestures.HOLD_S)

    media = REPO / "tasks" / "jumper" / task / "media"
    dest = media / f"{name}.npz"
    others = [p for p in media.glob("*.npz") if p != dest] if media.exists() else []
    if others:
        # The trainer finds the clip by extension, exactly one per directory.
        raise ValueError(f"{media} already holds {[p.name for p in others]}; remove it first")
    media.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dest, **out)

    body = n - len(lead_in) - len(lead_out) - len(hold)
    print(f"{path.name} -> {dest.relative_to(REPO)}")
    print(f"  {body} rows at {1.0 / dt:.0f} Hz = {body * dt:.2f} s, plus {t_in:.2f} s in, "
          f"{t_out:.2f} s out, {gestures.HOLD_S:.2f} s held = {n * dt:.2f} s")
    print(f"  base z {pose[:, 2].min() * 1000:.0f}..{pose[:, 2].max() * 1000:.0f} mm, "
          f"tilt at most {np.degrees(np.abs(pose[:, 3:5]).max()):.1f} deg, "
          f"travels {np.hypot(*np.ptp(pose[:, :2], axis=0)) * 1000:.0f} mm")
    print("  off the floor: " + ", ".join(f"{f} {v * 100:.0f}%" for f, v in lifted.items()))
    if lift.any():
        airborne = (height.min(axis=1) > gestures.DOWN_TOL).sum() * dt
        print(f"  jumps: up to {lift.max() * 1000:.0f} mm, {airborne:.2f} s airborne in all")
    for when, rate in found:
        print(f"  eased a snap: the body tipped {rate:.0f} deg/s at {when:.2f} s, where the "
              f"feet it rests on change")
    for when, rate in snaps(pose, dt):
        print(f"  WARNING: the body still tips {rate:.0f} deg/s at {when:.2f} s after easing "
              f"{eased}; key a path that sets the robot down there")
    for jname, by in clamped:
        print(f"  clamped {jname} by up to {by * 1000:.1f} mrad")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("keyframes", type=Path, help="a .keyframes.json from export_keyframes.py")
    ap.add_argument("--task", required=True, help="task directory under tasks/jumper/")
    ap.add_argument("--name", help="clip name (default: the table's name)")
    args = ap.parse_args(argv)
    convert(args.keyframes.resolve(), args.task, args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

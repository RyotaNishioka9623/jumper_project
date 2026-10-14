"""What every janken clip shares: the poses, and the opening up to the scissors.

Imported by the `make_janken_*.py` scripts, which Blender runs against the rig. Every
outcome (lose, win, draw) plays the same opening, so the cut between them in the
edit is seamless; only what follows frame `OPENING_END` differs.

Joint values are radians. Arm joints J0, J2, J3 and J4 change sign between the left
and right claws, J1 does not; leg joints all change sign. Poses that move the body
were checked with the converter's resting-floor solver (`keyframes_to_npz.py`):
heights are the base's, against HOME's 106.5 mm.
"""

from __future__ import annotations

import bpy

J = {o["joint"]: o for o in bpy.data.objects if "joint" in o}
HOME = {n: o.rotation_euler[o["axis"]] for n, o in J.items()}

#: Four legs, leaning back as the official `gesture_hello` does at its peak (mirrored
#: onto the right claw), so a raised right claw does not tip the robot: 115 mm.
LEAN = {
    "LF_J0_joint": -0.5236, "LF_J1_joint": -0.8727, "LF_J2_joint": -0.6109,
    "LF_J3_joint": -1.5708,
    "LM_J0_joint": -0.4166, "LM_J1_joint": 0.248, "LM_J2_joint": -1.6407,
    "RM_J0_joint": 0.4175, "RM_J1_joint": -0.2489, "RM_J2_joint": 1.6439,
    "LR_J0_joint": 0.1694, "LR_J1_joint": 0.5996, "LR_J2_joint": -1.9041,
    "RR_J0_joint": -0.1698, "RR_J1_joint": -0.6012, "RR_J2_joint": 1.9079,
}

#: The right claw held up beside the face, closed, like a raised fist.
CLAW_UP = {"RF_J0_joint": 0.4, "RF_J1_joint": -2.9, "RF_J2_joint": 0.6, "RF_J3_joint": 0.6,
           "RF_J4_joint": 0.0}
#: Scissors: the claw turned toward the viewer and opened, a V. 1.5 rather than the
#: 1.6 stop keeps `RF_J4` inside its soft limit.
SCISSORS = {"RF_J0_joint": 0.6, "RF_J1_joint": -3.1, "RF_J2_joint": 0.5, "RF_J3_joint": 0.3,
            "RF_J4_joint": 1.5}
#: The claw folded in front of the face, closed: hiding.
COVER = {"RF_J0_joint": 0.5, "RF_J1_joint": -2.4, "RF_J2_joint": 1.2, "RF_J3_joint": 0.8,
         "RF_J4_joint": 0.0}

#: The middle and rear legs' J1 moved together from LEAN (left by +d, right by -d):
#: +0.15 sinks to 104 mm, -0.25 rises to 130 mm, on the same four feet.
def legs_j1(d: float) -> dict[str, float]:
    out = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        for leg in ("M", "R"):
            name = f"{side}{leg}_J1_joint"
            out[name] = LEAN[name] + sign * d
    return out


#: The last frame of the shared opening; each outcome continues from here.
OPENING_END = 86


def key(frame: int, *layers: dict[str, float]) -> None:
    pose = dict(HOME)
    for layer in layers:
        pose.update(layer)
    for name, obj in J.items():
        obj.rotation_euler[obj["axis"]] = pose[name]
        obj.keyframe_insert("rotation_euler", index=obj["axis"], frame=frame)


def opening() -> None:
    """HOME, ready, "jan", "ken", "pon" -- scissors -- and a snip-snip, to frame 86."""
    for obj in J.values():
        obj.animation_data_clear()
    key(1)
    key(20, LEAN, CLAW_UP)
    # jan, ken: down on the beat, back up between.
    for f, j1 in ((32, -2.5), (38, -3.0), (44, -2.5), (50, -3.0)):
        key(f, LEAN, CLAW_UP, {"RF_J1_joint": j1})
    key(56, LEAN, SCISSORS)
    for f, j4 in ((62, 0.8), (68, 1.5), (74, 0.8), (80, 1.5)):
        key(f, LEAN, SCISSORS, {"RF_J4_joint": j4})
    key(OPENING_END, LEAN, SCISSORS)


def save(path, last_frame: int) -> None:
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, last_frame
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print(f"saved {path}")

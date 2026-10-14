"""Keyframe the first cut of `janken_lose` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_lose.py

Writes `scissors_crab/motions/janken_lose.blend`. From there the .blend is the source:
open it, adjust the keys in Blender, and export as usual (README). Re-running this
script overwrites the .blend, so it is only for starting over.

The right claw plays (`RF_*`); the robot stands on four legs and the left claw, leaning
back as the official `gesture_hello` does, so the raised claw does not tip it.

    frame  (30 fps)
    1      HOME
    20     ready: lean back, right claw held up beside the face, closed like a fist
    32-50  "jan" "ken": the claw swings down and up, twice
    56     "pon": turned toward the viewer and opened -- scissors, a V
    62-80  snip, snip: the scissors open and close, so nobody can miss them
    90     the opponent shows rock: a flinch
    100-125  the claw sinks, the scissors close, the body slumps on five feet
    125-155  hold, drooping a little further
"""

from __future__ import annotations

from pathlib import Path

import bpy

OUT = Path(__file__).resolve().with_name("janken_lose.blend")

J = {o["joint"]: o for o in bpy.data.objects if "joint" in o}
HOME = {n: o.rotation_euler[o["axis"]] for n, o in J.items()}

#: Four legs and the left claw: gesture_hello's lean at its peak, mirrored onto the
#: right claw (arm joints J0, J2, J3 change sign between sides, J1 does not).
LEAN = {
    "LF_J0_joint": -0.5236, "LF_J1_joint": -0.8727, "LF_J2_joint": -0.6109,
    "LF_J3_joint": -1.5708,
    "LM_J0_joint": -0.4166, "LM_J1_joint": 0.248, "LM_J2_joint": -1.6407,
    "RM_J0_joint": 0.4175, "RM_J1_joint": -0.2489, "RM_J2_joint": 1.6439,
    "LR_J0_joint": 0.1694, "LR_J1_joint": 0.5996, "LR_J2_joint": -1.9041,
    "RR_J0_joint": -0.1698, "RR_J1_joint": -0.6012, "RR_J2_joint": 1.9079,
}

#: The right claw held up beside the face, closed, like a raised fist; `RF_J1` lifts it.
CLAW_UP = {"RF_J0_joint": 0.4, "RF_J1_joint": -2.9, "RF_J2_joint": 0.6, "RF_J3_joint": 0.6,
           "RF_J4_joint": 0.0}
#: Scissors: the claw turned toward the viewer and opened (`RF_J4`), a V. 1.5 rather than
#: the 1.6 stop keeps it inside the soft limit.
SCISSORS = {"RF_J0_joint": 0.6, "RF_J1_joint": -3.1, "RF_J2_joint": 0.5, "RF_J3_joint": 0.3,
            "RF_J4_joint": 1.5}

#: Slumped. At HOME the claws carry weight, so folding the legs alone only lifts them;
#: the left claw folds too (`LF_J1`), and the body sinks on five feet. Searched with the
#: converter's own resting-floor solver: 92 mm against HOME's 106.5 (the lean is 115),
#: nose down 2.5 degrees, every joint inside its soft limit.
SLUMP = {
    "LF_J0_joint": -0.5507, "LF_J1_joint": -1.2658, "LF_J2_joint": -0.4408, "LF_J3_joint": -1.374,
    "LM_J0_joint": 0.0012, "LM_J1_joint": 0.7356, "LM_J2_joint": -1.8271,
    "RM_J0_joint": -0.0012, "RM_J1_joint": -0.7376, "RM_J2_joint": 1.8313,
    "LR_J0_joint": 0.6313, "LR_J1_joint": 0.6534, "LR_J2_joint": -1.8648,
    "RR_J0_joint": -0.6326, "RR_J1_joint": -0.6548, "RR_J2_joint": 1.8678,
}
#: A little further: 91 mm, nose down 2.0 degrees.
SLUMP_DEEPER = {"LM_J1_joint": 0.8356, "LM_J2_joint": -2.0271, "RM_J1_joint": -0.8376,
                "RM_J2_joint": 2.0313, "LR_J1_joint": 0.7534, "LR_J2_joint": -1.9648,
                "RR_J1_joint": -0.7548, "RR_J2_joint": 1.9678}
CLAW_DOWN = {"RF_J0_joint": 0.45, "RF_J1_joint": -1.25, "RF_J2_joint": 0.6, "RF_J3_joint": 1.5,
             "RF_J4_joint": 0.25}


def key(frame: int, *layers: dict[str, float]) -> None:
    pose = dict(HOME)
    for layer in layers:
        pose.update(layer)
    for name, obj in J.items():
        obj.rotation_euler[obj["axis"]] = pose[name]
        obj.keyframe_insert("rotation_euler", index=obj["axis"], frame=frame)


def main() -> None:
    for obj in J.values():
        obj.animation_data_clear()

    key(1)
    key(20, LEAN, CLAW_UP)
    # jan, ken: down on the beat, back up between.
    for f, j1 in ((32, -2.5), (38, -3.0), (44, -2.5), (50, -3.0)):
        key(f, LEAN, CLAW_UP, {"RF_J1_joint": j1})
    # pon: scissors.
    key(56, LEAN, SCISSORS)
    for f, j4 in ((62, 0.8), (68, 1.5), (74, 0.8), (80, 1.5)):
        key(f, LEAN, SCISSORS, {"RF_J4_joint": j4})
    key(86, LEAN, SCISSORS)
    # Rock: a small flinch back.
    key(90, LEAN, SCISSORS, {"RF_J1_joint": -3.3, "RF_J0_joint": 0.45})
    key(100, LEAN, SCISSORS, {"RF_J1_joint": -2.9, "RF_J4_joint": 1.1})
    # Lose: everything sinks.
    key(125, LEAN, SLUMP, CLAW_DOWN)
    key(155, LEAN, SLUMP, SLUMP_DEEPER, CLAW_DOWN, {"RF_J1_joint": -1.15})

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 155
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
    print(f"saved {OUT}")


main()

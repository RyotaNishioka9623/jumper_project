"""Keyframe the first cut of `janken_lose` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_lose.py

Writes `scissors_crab/motions/janken_lose.blend`. From there the .blend is the source:
open it, adjust the keys in Blender, and export as usual (README). Re-running this
script overwrites the .blend, so it is only for starting over.

    frame  (30 fps)
    1-86     the shared opening (janken_common.py): ready, "jan", "ken", "pon" --
             scissors -- and a snip-snip
    90       the opponent shows rock: a flinch
    100-125  the claw sinks, the scissors close, the body slumps on five feet
    125-155  hold, drooping a little further
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from janken_common import LEAN, SCISSORS, key, opening, save

OUT = Path(__file__).resolve().with_name("janken_lose.blend")

#: Slumped. Folding the legs alone would only lift them off the floor while the left
#: claw holds the body up, so the left claw folds too (`LF_J1`) and the body sinks on
#: five feet. Searched with the converter's resting-floor solver: 92 mm (the lean is
#: 115), nose down 2.5 degrees, every joint inside its soft limit.
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


def main() -> None:
    opening()
    # Rock: a small flinch back.
    key(90, LEAN, SCISSORS, {"RF_J1_joint": -3.3, "RF_J0_joint": 0.45})
    key(100, LEAN, SCISSORS, {"RF_J1_joint": -2.9, "RF_J4_joint": 1.1})
    # Lose: everything sinks.
    key(125, LEAN, SLUMP, CLAW_DOWN)
    key(155, LEAN, SLUMP, SLUMP_DEEPER, CLAW_DOWN, {"RF_J1_joint": -1.15})
    save(OUT, 155)


main()

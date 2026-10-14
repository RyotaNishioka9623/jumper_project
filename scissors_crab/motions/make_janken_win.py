"""Keyframe the first cut of `janken_win` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_win.py

Writes `scissors_crab/motions/janken_win.blend`; see make_janken_lose.py for how the
.blend takes over from here.

    frame  (30 fps)
    1-86     the shared opening (janken_common.py), ending on scissors
    92       the opponent shows paper: the claw jumps up -- it won
    98-128   bouncing with joy, the scissors snipping on every bounce
    132      it remembers itself
    146-160  the claw comes in front of the face: hiding, fidgeting a little
    170      a peek past the claw
    180-200  hidden again
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from janken_common import COVER, LEAN, SCISSORS, key, legs_j1, opening, save

OUT = Path(__file__).resolve().with_name("janken_win.blend")

#: The bounce, on LEAN's four feet: 104 mm down, 130 mm up.
DOWN, UP = legs_j1(0.15), legs_j1(-0.25)
#: Shrinking a little while hiding: 109 mm.
SHRINK = legs_j1(0.08)
#: The claw moved aside from the face, enough for one eye.
PEEK = {**COVER, "RF_J0_joint": 0.3, "RF_J1_joint": -2.55}


def main() -> None:
    opening()
    # Paper: it won.
    key(92, LEAN, SCISSORS, {"RF_J1_joint": -3.3})
    # Bounce, snipping.
    for f, legs, j4 in ((98, DOWN, 0.8), (104, UP, 1.5), (110, DOWN, 0.8), (116, UP, 1.5),
                        (122, DOWN, 0.8), (128, {}, 1.5)):
        key(f, LEAN, legs, SCISSORS, {"RF_J4_joint": j4})
    # ... and remembers itself.
    key(132, LEAN, SCISSORS, {"RF_J1_joint": -2.95, "RF_J4_joint": 1.2})
    # Hide.
    key(146, LEAN, SHRINK, COVER)
    key(153, LEAN, SHRINK, COVER, {"RF_J0_joint": 0.55})
    key(160, LEAN, SHRINK, COVER)
    # Peek.
    key(170, LEAN, SHRINK, PEEK)
    key(176, LEAN, SHRINK, PEEK)
    # Hidden again.
    key(182, LEAN, SHRINK, COVER)
    key(200, LEAN, SHRINK, COVER)
    save(OUT, 200)


main()

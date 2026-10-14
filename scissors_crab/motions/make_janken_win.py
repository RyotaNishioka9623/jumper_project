"""Keyframe the first cut of `janken_win` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_win.py

Writes `scissors_crab/motions/janken_win.blend`; see make_janken_lose.py for how the
.blend takes over from here.

    frame  (30 fps)
    1-112    the shared opening (janken_common.py): a practice snip, the game, "pon"
    E+4      (E = the opening's last frame) the opponent shows paper: the claw jumps
             up -- it won
    E+12-52  bouncing with joy, the scissors snipping for real this time
    E+56     it remembers itself
    E+70-84  the claw comes in front of the face: hiding, fidgeting a little
    E+94     a peek past the claw
    E+106-124 hidden again
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
    e = opening()
    # Paper: it won.
    key(e + 4, LEAN, SCISSORS, {"RF_J1_joint": -3.3})
    # Bounce, snipping with joy: 0.5 s a snip, one bounce each.
    for f, legs, j4 in ((12, DOWN, 0.8), (20, UP, 1.5), (28, DOWN, 0.8), (36, UP, 1.5),
                        (44, DOWN, 0.8), (52, {}, 1.5)):
        key(e + f, LEAN, legs, SCISSORS, {"RF_J4_joint": j4})
    # ... and remembers itself.
    key(e + 56, LEAN, SCISSORS, {"RF_J1_joint": -2.95, "RF_J4_joint": 1.2})
    # Hide.
    key(e + 70, LEAN, SHRINK, COVER)
    key(e + 77, LEAN, SHRINK, COVER, {"RF_J0_joint": 0.55})
    key(e + 84, LEAN, SHRINK, COVER)
    # Peek.
    key(e + 94, LEAN, SHRINK, PEEK)
    key(e + 100, LEAN, SHRINK, PEEK)
    # Hidden again.
    key(e + 106, LEAN, SHRINK, COVER)
    key(e + 124, LEAN, SHRINK, COVER)
    save(OUT, e + 124)


main()

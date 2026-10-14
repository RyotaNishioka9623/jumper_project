"""Keyframe the first cut of `janken_draw` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_draw.py

Writes `scissors_crab/motions/janken_draw.blend`; see make_janken_lose.py for how the
.blend takes over from here.

The opponent is another crab, so it throws scissors too: a draw, and again, and again.
In the video two robots face each other playing this clip, one mirrored, in step, and
the draws go on until the picture fades out. Each "aiko de sho" cycle starts and ends
on the scissors pose, so the edit can repeat a cycle for as long as it likes.

    frame  (30 fps)
    1-86     the shared opening (janken_common.py), ending on scissors
    90       the opponent shows scissors too: a flinch
    100      on guard again
    100+36k  cycle k of three: "ai" (down), up, "ko de" (down), "sho!" (scissors,
             frame +24), a snip, and back to scissors at +36
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from janken_common import CLAW_UP, LEAN, SCISSORS, key, opening, save

OUT = Path(__file__).resolve().with_name("janken_draw.blend")

CYCLE = 36
CYCLES = 3
FIRST = 100


def main() -> None:
    opening()
    # Scissors against scissors.
    key(90, LEAN, SCISSORS, {"RF_J1_joint": -3.3, "RF_J0_joint": 0.45})
    key(96, LEAN, SCISSORS, {"RF_J4_joint": 1.2})
    key(FIRST, LEAN, SCISSORS)
    for k in range(CYCLES):
        s = FIRST + k * CYCLE
        for offset, j1 in ((6, -2.5), (12, -3.0), (18, -2.5)):
            key(s + offset, LEAN, CLAW_UP, {"RF_J1_joint": j1})
        key(s + 24, LEAN, SCISSORS)
        key(s + 30, LEAN, SCISSORS, {"RF_J4_joint": 0.8})
        key(s + CYCLE, LEAN, SCISSORS)
    save(OUT, FIRST + CYCLES * CYCLE)


main()

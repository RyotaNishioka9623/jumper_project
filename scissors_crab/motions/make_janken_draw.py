"""Keyframe the first cut of `janken_draw` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_draw.py

Writes `scissors_crab/motions/janken_draw.blend`; see make_janken_lose.py for how the
.blend takes over from here.

The opponent is another crab, so it throws scissors too: a draw, and again, and again.
In the video two robots face each other playing this clip, one mirrored, in step, and
the draws go on until the picture fades out. Each "aiko de sho" cycle starts and ends
on the scissors pose, so the edit can repeat a cycle for as long as it likes.

Unlike lose and win, nothing here reacts: no snip, no flinch at the other crab's
scissors, the eyes serious throughout. Two crabs frozen on scissors, staring each other
down and going again without a word, is the joke.

    frame  (30 fps)
    1-112    the opening with the practice V held still (janken_common.py), "pon"
    E-E+14   (E = its last frame) held still on scissors
    E+14+36k cycle k of three: "ai" (down), up, "ko de" (down), "sho!" (scissors,
             frame +24), held still, back on scissors at +36
    then     set down to HOME, the claws first (janken_common.set_down)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from janken_common import CLAW_UP, LEAN, SCISSORS, key, opening, save, set_down

OUT = Path(__file__).resolve().with_name("janken_draw.blend")

CYCLE = 36
CYCLES = 3


def main() -> None:
    e = opening(snips=False)
    # Scissors against scissors: nothing moves.
    first = e + 14
    key(first, LEAN, SCISSORS)
    for k in range(CYCLES):
        s = first + k * CYCLE
        for offset, j1 in ((6, -2.5), (12, -3.0), (18, -2.5)):
            key(s + offset, LEAN, CLAW_UP, {"RF_J1_joint": j1})
        key(s + 24, LEAN, SCISSORS)
        key(s + CYCLE, LEAN, SCISSORS)
    save(OUT, set_down(first + CYCLES * CYCLE))


main()

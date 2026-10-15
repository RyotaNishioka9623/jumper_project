"""Keyframe the first cut of `janken_win` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_win.py

Writes `scissors_crab/motions/janken_win.blend`; see make_janken_lose.py for how the
.blend takes over from here.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_win.py -- --hop deep

writes `janken_win_hop.blend` instead, for the task `jumper.janken_win_hop`: the same
take with a jump made to be learnable. The first cut's hop (crouch 104 mm, a 0.07 s
eased push, 0.2 s and 49 mm in the air) came out of training as a bounce, the feet
leaving the floor by 5 mm: the push ended at rest and the body was asked to fly at
1 m/s from it. The deep hop crouches to 83 mm, pushes for 0.13 s accelerating (quad
ease-in), and flies 0.17 s, 34 mm.

Winning is carried away, then embarrassed by it: both claws go up in a double V, two
hops, a double snip -- and then it remembers itself and hides its face in both claws.

    frame  (30 fps; E = the opening's last frame, 112)
    1-E      the shared opening (janken_common.py): a practice snip, the game, "pon"
    E+4      the opponent shows paper: the claw jumps up -- it won
    E+10     both claws up, a double V, crouched
    E+13-19  hop (0.2 s in the air, 49 mm), landing on extended legs, crouch
    E+26-32  hop again
    E+40-48  standing, a double snip
    E+52     it remembers itself
    E+62-76  both claws over the face, fidgeting
    E+86-92  the right claw moves aside: a peek
    E+98-116 hidden again
    E+150    set down to HOME, the claws first (janken_common.set_down)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from janken_common import COVER, LEAN, SCISSORS, hop, key, legs_j1, mirror, opening, save, set_down

HERE = Path(__file__).resolve().parent

#: On LEAN's four feet: crouched 104 mm, legs extended 130 mm (the take-off and the
#: landing), a little shrunk while hiding 109 mm; the deep hop's crouch, 83 mm.
DOWN, UP, SHRINK = legs_j1(0.15), legs_j1(-0.25), legs_j1(0.08)
DEEP = legs_j1(0.25, 0.20)
BOTH_V = {**SCISSORS, **mirror(SCISSORS)}
BOTH_CLOSED = {**BOTH_V, "RF_J4_joint": 0.8, "LF_J4_joint": -0.8}
#: Both claws over the face; J0 0.45 rather than COVER's 0.5 leaves them a gap.
HIDE = {**COVER, "RF_J0_joint": 0.45}
BOTH_HIDE = {**HIDE, **mirror(HIDE)}
#: The right claw aside, the left still covering: one eye peeks out.
PEEK = {**BOTH_HIDE, "RF_J0_joint": 0.15, "RF_J1_joint": -2.7}


def first_hops(e: int) -> int:
    """The first cut's two hops; returns the frame it stands up again."""
    key(e + 10, LEAN, DOWN, BOTH_V)
    for takeoff in (e + 13, e + 26):
        key(takeoff - 2, LEAN, DOWN, BOTH_V)       # crouched until the push
        key(takeoff, LEAN, UP, BOTH_V)             # legs out: off the floor
        hop(takeoff, takeoff + 6)
        key(takeoff + 6, LEAN, UP, BOTH_V)         # landing on extended legs
        key(takeoff + 10, LEAN, DOWN, BOTH_V)      # absorbed
    return e + 40


def deep_hops(e: int) -> int:
    """Two learnable hops: a deep crouch, an accelerating push, a shorter flight."""
    key(e + 10, LEAN, DEEP, BOTH_V)
    for takeoff in (e + 14, e + 28):
        key(takeoff - 4, LEAN, DEEP, BOTH_V, interp="QUAD")  # push, accelerating
        key(takeoff, LEAN, UP, BOTH_V)                       # legs out: off the floor
        hop(takeoff, takeoff + 5)
        key(takeoff + 5, LEAN, UP, BOTH_V)                   # landing
        key(takeoff + 10, LEAN, DEEP, BOTH_V)                # absorbed
    return e + 42


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--hop", choices=("first", "deep"), default="first")
    deep = ap.parse_args(argv).hop == "deep"

    e = opening()
    # Paper: it won.
    key(e + 4, LEAN, SCISSORS, {"RF_J1_joint": -3.3})
    # Carried away: double V, crouch, hop, hop.
    stand = deep_hops(e) if deep else first_hops(e)
    # Standing, a double snip.
    key(stand, LEAN, BOTH_V)
    key(e + 44 if stand < e + 44 else stand + 3, LEAN, BOTH_CLOSED)
    key(e + 48, LEAN, BOTH_V)
    # ... and remembers itself.
    key(e + 52, LEAN, BOTH_V)
    # Hide in both claws.
    key(e + 62, LEAN, SHRINK, BOTH_HIDE)
    key(e + 69, LEAN, SHRINK, BOTH_HIDE, {"RF_J0_joint": 0.5, "LF_J0_joint": -0.5})
    key(e + 76, LEAN, SHRINK, BOTH_HIDE)
    # Peek.
    key(e + 86, LEAN, SHRINK, PEEK)
    key(e + 92, LEAN, SHRINK, PEEK)
    # Hidden again.
    key(e + 98, LEAN, SHRINK, BOTH_HIDE)
    key(e + 116, LEAN, SHRINK, BOTH_HIDE)
    out = HERE / ("janken_win_hop.blend" if deep else "janken_win.blend")
    save(out, set_down(e + 116))


main()

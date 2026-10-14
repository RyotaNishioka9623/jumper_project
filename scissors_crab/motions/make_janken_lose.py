"""Keyframe the first cut of `janken_lose` on the rig, as a starting point to refine by hand.

    blender scissors_crab/blender/jumper_rig.blend --background \
        --python scissors_crab/motions/make_janken_lose.py

Writes `scissors_crab/motions/janken_lose.blend`. From there the .blend is the source:
open it, adjust the keys in Blender, and export as usual (README). Re-running this
script overwrites the .blend, so it is only for starting over.

Losing is told slowly, so it reads: a flinch at the rock, a frozen blank stare with
the scissors still up, the head sinking on its own while the scissors wilt, and only
then the tears -- the claw dropping and the body hitching with sobs.

    frame  (30 fps; E = the opening's last frame, 116)
    1-E      the shared opening (janken_common.py): ready, "jan", "ken", "pon" --
             scissors, held -- and two slow snips
    E+4      the opponent shows rock: a flinch
    E+10-30  frozen on the scissors
    E+30-75  the head sinks (the body pitches nose down 17 degrees, the rear stays up),
             the scissors wilt
    E+85-100 the claw drops: crying
    E+100-150 two pairs of sobs
    E+170    end
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from janken_common import LEAN, SCISSORS, key, opening, save

OUT = Path(__file__).resolve().with_name("janken_lose.blend")

#: Head down, from LEAN: the rear legs straighten (J1) and the middle legs and the left
#: claw fold, so the front sinks and the rear stays up. Searched with the converter's
#: resting-floor solver: nose down 16.8 degrees (the lean is 8 degrees nose up),
#: 108 mm, on five feet, every joint inside its soft limit.
HEAD_DOWN = {"LF_J1_joint": -1.4727, "LM_J2_joint": -1.0407, "RM_J2_joint": 1.0439,
             "LR_J1_joint": -0.0004, "LR_J2_joint": -1.6041, "RR_J1_joint": -0.0012,
             "RR_J2_joint": 1.6079}
#: The scissors half lowered, half closed.
WILT = {"RF_J0_joint": 0.5, "RF_J1_joint": -2.6, "RF_J2_joint": 0.6, "RF_J3_joint": 0.6,
        "RF_J4_joint": 0.6}
#: The claw hanging: 25 mm off the floor with the body pitched down (-1.6 would touch).
DROOP = {"RF_J0_joint": 0.45, "RF_J1_joint": -1.75, "RF_J2_joint": 0.6, "RF_J3_joint": 1.2,
         "RF_J4_joint": 0.2}


def sob(d: float) -> dict[str, float]:
    """A hitch: the middle legs' J2 moved by d from HEAD_DOWN (+0.08 dips the head to
    17.2 degrees, -0.08 lifts it to 14.9)."""
    return {"LM_J2_joint": HEAD_DOWN["LM_J2_joint"] + d,
            "RM_J2_joint": HEAD_DOWN["RM_J2_joint"] - d}


def main() -> None:
    e = opening()
    # Rock: a flinch, then frozen.
    key(e + 4, LEAN, SCISSORS, {"RF_J1_joint": -3.3, "RF_J0_joint": 0.45})
    key(e + 10, LEAN, SCISSORS)
    key(e + 30, LEAN, SCISSORS)
    # The head sinks, slowly; the scissors wilt.
    key(e + 75, LEAN, HEAD_DOWN, WILT)
    key(e + 85, LEAN, HEAD_DOWN, WILT)
    # Crying.
    key(e + 100, LEAN, HEAD_DOWN, DROOP)
    for f, d in ((105, 0.08), (110, -0.08), (115, 0.08), (120, 0.0),
                 (135, 0.08), (140, -0.08), (145, 0.08), (150, 0.0)):
        key(e + f, LEAN, HEAD_DOWN, DROOP, sob(d))
    key(e + 170, LEAN, HEAD_DOWN, DROOP)
    save(OUT, e + 170)


main()

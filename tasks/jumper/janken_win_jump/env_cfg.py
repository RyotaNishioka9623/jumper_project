"""Environment config for jumper.janken_win_jump: `jumper.janken_win_hop`'s, and inside
the jump window the terms `tasks/jumper/common/janken_jump.py` adds. Every number
the jump terms use is below, with what it was measured on."""

from __future__ import annotations

from pathlib import Path

from mjlab.envs import ManagerBasedRlEnvCfg

from ..common.janken import BUDGET
from ..common.janken_jump import janken_jump_env_cfg

MEDIA = Path(__file__).resolve().parent / "media"

#: A support foot is off the floor when its site is this far above where it stands.
#: In the clip, planted feet sit within 0.95 mm of their lowest (90th percentile over
#: all frames) and the hops clear 33.6 mm; at 3 mm the two airborne runs are 8 and 7
#: control steps, and every foot leaves and lands on the same step.
CLEARANCE_M = 0.003

#: The window opens this long before the first take-off and closes this long after
#: the last landing. In the clip the crouch into the first hop starts 0.34 s before
#: it leaves the floor (frames 212 -> 229 at 50 Hz), and the body is back at its
#: standing height 0.32 s after the second landing (260 -> 276); both are rounded up,
#: so the penalties stay off through the whole push-off and the whole absorption.
LEAD_S = 0.4
TAIL_S = 0.4

#: `jumper.jump`'s kernels as fractions of its own reference's amplitude, applied to
#: this clip's. Its height kernel is 1/e at 50 mm against a 163.0 mm crouch-to-apex;
#: its velocity kernel at sqrt(0.30) = 0.548 m/s against a 1.684 m/s peak (both
#: measured on `tasks/jumper/jump/ref/high_jump_flat.npz`). This clip crouches to 83
#: mm and peaks at 163 mm, 0.82 m/s, so 24.5 mm and 0.27 m/s: a 33 mm miss at the
#: apex -- `jumper.janken_win_hop`'s -- scores 0.16 where mjlab's anchor term gives 0.99.
HEIGHT_SIGMA_RATIO = 0.050 / 0.163
VZ_SIGMA_RATIO = 0.30**0.5 / 1.684

#: In `jumper.jump` the three terms that are the jump -- height 3.0, velocity 2.0,
#: contact 2.5 -- are as much positive reward as its other imitation terms together
#: (joint position 3.0, foot position 2.0, orientation 1.5, joint velocity 1.0). The
#: same proportion here: inside the window they add another `BUDGET` (6.5) a step,
#: split 3 : 2 : 2.5.
HEIGHT_WEIGHT = round(BUDGET * 3.0 / 7.5, 2)
VZ_WEIGHT = round(BUDGET * 2.0 / 7.5, 2)
CONTACT_WEIGHT = round(BUDGET * 2.5 / 7.5, 2)

#: A foot is in contact above this normal force, as in `jumper.jump`. Standing on its
#: four support feet, the robot puts about a quarter of its 25 N (2.54 kg) on each.
CONTACT_FORCE_N = 1.0


def env_cfg(asset: Path | None = None, play: bool = False) -> ManagerBasedRlEnvCfg:
    """Build this task's environment config. See `jumper.dance`'s for the arguments."""
    return janken_jump_env_cfg(
        MEDIA, asset, play,
        clearance_m=CLEARANCE_M,
        lead_s=LEAD_S,
        tail_s=TAIL_S,
        height_sigma_ratio=HEIGHT_SIGMA_RATIO,
        vz_sigma_ratio=VZ_SIGMA_RATIO,
        height_weight=HEIGHT_WEIGHT,
        vz_weight=VZ_WEIGHT,
        contact_weight=CONTACT_WEIGHT,
        contact_force_n=CONTACT_FORCE_N,
    )

"""jumper.janken_win_hop -- janken_win with a jump made to be learnable.

The same take as `jumper.janken_win`, keyframed by
`scissors_crab/motions/make_janken_win.py --hop deep`. The first cut's hops trained into
a bounce (the feet left the floor by 5 mm); these crouch deeper (83 mm), push for
0.13 s accelerating, and fly 0.17 s, 34 mm. `jumper.janken_win` and its trained policy
are kept as they are, to compare.

The clip is `media/janken_win_hop.npz`. The environment's numbers are measured from it
(`tasks/jumper/common/janken.py`). There is no music. Export with `--no-video`.
"""

from __future__ import annotations

from ...registry import register
from ..common.assets import JUMPER_ASSETS

register(
    id="jumper.janken_win_hop",
    assets=JUMPER_ASSETS,
    description="jumper hexapod imitating a keyframed janken win with learnable hops; the "
                "clip is committed in tasks/jumper/janken_win_hop/media/",
    tags=("imitation", "jumper", "gesture", "flat"),
)

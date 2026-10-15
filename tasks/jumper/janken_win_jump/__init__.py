"""jumper.janken_win_jump -- janken_win_hop with the jump asked for.

The same clip as `jumper.janken_win_hop` (`media/janken_win_jump.npz` is the same
keyframe table converted again, byte-identical in every channel). That task tracked
it to 1.6 degrees and never left the floor; this one keeps its environment and adds,
inside the jump window only, what `jumper.jump` rewards and what the dance machinery
charges against (`tasks/jumper/common/janken_jump.py`). `jumper.janken_win_hop` and
its trained policy are kept as they are, to compare.

There is no music. Export with `--no-video`.
"""

from __future__ import annotations

from ...registry import register
from ..common.assets import JUMPER_ASSETS

register(
    id="jumper.janken_win_jump",
    assets=JUMPER_ASSETS,
    description="jumper hexapod imitating a keyframed janken win, rewarded for leaving the "
                "floor through its hops; the clip is committed in "
                "tasks/jumper/janken_win_jump/media/",
    tags=("imitation", "jumper", "gesture", "flat"),
)

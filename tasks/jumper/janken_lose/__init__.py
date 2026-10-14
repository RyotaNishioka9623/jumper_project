"""jumper.janken_lose -- throws scissors, loses to rock, and droops.

A one-shot gesture on the dance machinery, keyframed in Blender
(`scissors_crab/blender/`) and converted with `scissors_crab/tools/keyframes_to_npz.py`:
the robot leans back on four legs, shakes its right claw three times, throws
scissors -- the only hand a crab has -- and, losing, lowers the claw and sinks.

The clip is `media/janken_lose.npz`. The environment's numbers are measured from it
(`tasks/jumper/common/janken.py`). There is no music: the video gets captions and
sound effects in editing. Export with `--no-video`.
"""

from __future__ import annotations

from ...registry import register
from ..common.assets import JUMPER_ASSETS

register(
    id="jumper.janken_lose",
    assets=JUMPER_ASSETS,
    description="jumper hexapod imitating a keyframed janken: shakes, throws scissors, "
                "loses and droops; the clip is committed in tasks/jumper/janken_lose/media/",
    tags=("imitation", "jumper", "gesture", "flat"),
)

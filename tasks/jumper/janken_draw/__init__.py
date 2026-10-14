"""jumper.janken_draw -- throws scissors against another crab's scissors: a draw, again and again.

A one-shot gesture on the dance machinery, keyframed in Blender
(`scissors_crab/motions/make_janken_draw.py`) and converted with
`scissors_crab/tools/keyframes_to_npz.py`. It opens as `jumper.janken_lose` does, flinches
at the opponent's scissors, then plays three "aiko de sho" cycles -- swing, swing,
scissors, snip -- each starting and ending on the scissors pose, so a video can repeat
one for as long as the draws should last.

The clip is `media/janken_draw.npz`. The environment's numbers are measured from it
(`tasks/jumper/common/janken.py`). There is no music. Export with `--no-video`.
"""

from __future__ import annotations

from ...registry import register
from ..common.assets import JUMPER_ASSETS

register(
    id="jumper.janken_draw",
    assets=JUMPER_ASSETS,
    description="jumper hexapod imitating a keyframed janken: throws scissors, draws with "
                "scissors, and goes again; the clip is committed in tasks/jumper/janken_draw/media/",
    tags=("imitation", "jumper", "gesture", "flat"),
)

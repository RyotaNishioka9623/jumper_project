"""jumper.janken_win -- throws scissors, beats paper, bounces with joy, then hides, shy.

A one-shot gesture on the dance machinery, keyframed in Blender
(`scissors_crab/motions/make_janken_win.py`) and converted with
`scissors_crab/tools/keyframes_to_npz.py`. It opens as `jumper.janken_lose` does --
the same keys, so the two cut together -- then bounces on four legs with the scissors
snipping, remembers itself, folds the right claw in front of its face, peeks past it,
and hides again.

The clip is `media/janken_win.npz`. The environment's numbers are measured from it
(`tasks/jumper/common/janken.py`). There is no music. Export with `--no-video`.
"""

from __future__ import annotations

from ...registry import register
from ..common.assets import JUMPER_ASSETS

register(
    id="jumper.janken_win",
    assets=JUMPER_ASSETS,
    description="jumper hexapod imitating a keyframed janken: throws scissors, wins, "
                "bounces and hides shyly; the clip is committed in tasks/jumper/janken_win/media/",
    tags=("imitation", "jumper", "gesture", "flat"),
)

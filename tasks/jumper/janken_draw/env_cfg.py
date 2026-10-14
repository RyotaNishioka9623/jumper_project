"""Environment config for jumper.janken_draw: every number is measured from
`media/janken_draw.npz` by `tasks/jumper/common/janken.py`."""

from __future__ import annotations

from pathlib import Path

from mjlab.envs import ManagerBasedRlEnvCfg

from ..common.janken import janken_env_cfg

MEDIA = Path(__file__).resolve().parent / "media"


def env_cfg(asset: Path | None = None, play: bool = False) -> ManagerBasedRlEnvCfg:
    """Build this task's environment config. See `jumper.dance`'s for the arguments."""
    return janken_env_cfg(MEDIA, asset, play)

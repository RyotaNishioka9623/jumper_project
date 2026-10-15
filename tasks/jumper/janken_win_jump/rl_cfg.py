"""Hyper-parameters for jumper.janken_win_jump: gesture_paw's, via
`tasks/jumper/common/janken.py`."""

from __future__ import annotations

from mjlab.rl import RslRlOnPolicyRunnerCfg

from ..common.janken import janken_agent_cfg


def agent_cfg() -> RslRlOnPolicyRunnerCfg:
    """This task's rsl_rl config: `logs/<model>/jumper.janken_win_jump/<date-time>`."""
    return janken_agent_cfg("jumper.janken_win_jump")


def runner_cls() -> type:
    """mjlab's motion-tracking runner, as the gestures."""
    from mjlab.tasks.tracking.rl import MotionTrackingOnPolicyRunner

    return MotionTrackingOnPolicyRunner

"""The janken (rock-paper-scissors) gestures' shared environment: one builder, every
number derived from the clip.

The janken tasks (`jumper.janken_lose`, `_win`, `_draw`) are one-shot gestures on the
dance machinery, like `jumper.gesture_paw`, with clips keyframed in Blender
(`scissors_crab/`). Their clips are re-cut as the choreography is worked on, so the
clip-dependent numbers are not typed in per clip but measured here, with the rules
`jumper.dance` and `jumper.gesture_paw` wrote down for theirs:

- joint position std: 0.44 x the clip's RMS joint amplitude about its mean,
- joint velocity std: two thirds of the clip's joint velocity RMS,
- joint limit weight: the dances' -10 while the clip stays inside the soft limits
  (0.9 of the range about its centre); past them, small enough that tracking the
  clip faithfully costs at most ~8% of the 6.5 reward budget, as gesture_paw's -0.5,
- root height termination: 40 mm, or the clip's own height band plus 10 mm if wider,
- episode: half the clip, the rule for a short clip.

Everything else is gesture_paw's, for gesture_paw's reasons: they are properties of
the robot and the action space, not of a clip.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .dance.env import dance_env_cfg
from .dance.motion import LEG_JOINTS

#: The positive reward budget a step, as jumper.dance.
BUDGET = 6.5


@dataclass(frozen=True)
class ClipStats:
    duration_s: float
    pos_rms: float
    vel_rms: float
    height_band_m: float
    soft_limit_excess: float


def measure(media: Path, joint_range: np.ndarray | None = None) -> ClipStats:
    """Measure the one `.npz` in `media`. `joint_range` is [22, 2] in the clip's
    channel order; without it the soft-limit check is skipped."""
    (path,) = sorted(media.glob("*.npz"))
    with np.load(path) as z:
        dt = float(z["dt"])
        keys = [f"L{leg}_j{j}" for leg in sorted(LEG_JOINTS) for j in range(len(LEG_JOINTS[leg]))]
        q = np.stack([z[f"meas_{k}"] for k in keys], axis=1).astype(np.float64)
        height = np.asarray(z["meas_body_z"], dtype=np.float64)
    vel = np.diff(q, axis=0) / dt
    excess = 0.0
    if joint_range is not None:
        mid, half = joint_range.mean(axis=1), 0.45 * np.ptp(joint_range, axis=1)
        excess = float(np.maximum(np.abs(q - mid) - half, 0.0).sum(axis=1).max())
    return ClipStats(
        duration_s=len(q) * dt,
        pos_rms=float(np.sqrt(((q - q.mean(axis=0)) ** 2).mean())),
        vel_rms=float(np.sqrt((vel ** 2).mean())),
        height_band_m=float(np.ptp(height)),
        soft_limit_excess=excess,
    )


def _joint_range() -> np.ndarray:
    from .constants import get_spec

    model = get_spec(None).compile()
    names = [n for leg in sorted(LEG_JOINTS) for n in LEG_JOINTS[leg]]
    return np.array([model.jnt_range[model.joint(n).id] for n in names])


def janken_env_cfg(media: Path, asset: Path | None, play: bool):
    """The environment for the janken clip in `media`."""
    s = measure(media, _joint_range())
    limit_weight = -10.0 if s.soft_limit_excess == 0.0 else -min(
        10.0, 0.08 * BUDGET / s.soft_limit_excess)
    return dance_env_cfg(
        media=media,
        asset=asset,
        play=play,
        episode_s=max(2.0, round(s.duration_s / 2.0, 1)),
        rsi_pose_range={
            "x": (-0.01, 0.01), "y": (-0.01, 0.01), "z": (-0.005, 0.005),
            "roll": (-0.05, 0.05), "pitch": (-0.05, 0.05), "yaw": (-0.05, 0.05),
        },
        rsi_velocity_range={
            "x": (-0.1, 0.1), "y": (-0.1, 0.1), "z": (-0.05, 0.05),
            "roll": (-0.2, 0.2), "pitch": (-0.2, 0.2), "yaw": (-0.2, 0.2),
        },
        rsi_joint_range=(-0.05, 0.05),
        joint_pos_noise=0.01,
        joint_vel_noise=0.5,
        joint_pos_std=round(0.44 * s.pos_rms, 3),
        joint_pos_weight=1.0,
        joint_vel_std=round(2.0 / 3.0 * s.vel_rms, 3),
        joint_vel_weight=0.5,
        action_rate_weight=-0.1,
        action_acc_weight=-0.05,
        power_weight=-0.02,
        torque_headroom_weight=-2.0,
        joint_limit_weight=round(limit_weight, 3),
        self_collision_weight=-1.0,
        self_collision_force=1.0,
        anchor_height_error=max(0.04, s.height_band_m + 0.01),
        anchor_tilt_error=0.3,
        support_foot_error=0.05,
        push_interval_s=(3.0, 8.0),
        push_velocity_range={
            "x": (-0.1, 0.1), "y": (-0.1, 0.1), "z": (-0.05, 0.05),
            "roll": (-0.2, 0.2), "pitch": (-0.2, 0.2), "yaw": (-0.2, 0.2),
        },
    )


def janken_agent_cfg(experiment_name: str):
    """gesture_paw's hyper-parameters: one-armed, so no mirroring."""
    from .ppo import jumper_ppo_baseline

    return jumper_ppo_baseline(
        experiment_name=experiment_name,
        symmetry=False,
        use_data_augmentation=False,
        use_mirror_loss=False,
        actor_hidden_dims=(512, 256, 128, 64),
        critic_hidden_dims=(512, 256, 128, 64),
        init_std=1.0,
        entropy_coef=0.005,
        learning_rate=1.0e-3,
        desired_kl=0.01,
        gamma=0.99,
        lam=0.95,
        num_learning_epochs=5,
        num_mini_batches=4,
        num_steps_per_env=24,
        max_iterations=10_000,
    )

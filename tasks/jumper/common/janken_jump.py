"""The jump in a janken clip: where it is, and the reward that asks for it.

`jumper.janken_win_hop` tracked its clip to 1.6 degrees and never left the floor: the
hops it was keyframed with (34 mm clear of the floor) came out as a 47 mm bounce with
the feet 3.5 mm up. Two properties of the environment `janken_env_cfg` builds made
not jumping the better policy, and neither is a property of the robot --
`jumper.jump` clears 14 cm on the same model.

- **Jumping is charged for.** The dance's power term (-0.02 per W) and its torque
  headroom term (-2 per (N*m)^2 above the 1.2 N*m continuous rating) are there to keep
  a dance calm. A push-off is neither: priced on `jumper.jump`'s own reference
  (`tasks/jumper/jump/ref/high_jump_flat.npz`, its `tau` and `qd`), they would cost
  4.7 a step on average over the 0.2 s around take-off and 17.0 at the peak, against
  6.5 a step of positive reward at most.
- **Nothing pays for the height.** mjlab's tracking terms keep the G1's stds: 0.3 m
  on the anchor's position, so a 33 mm miss at the apex still scores 0.99, and
  1.0 m/s on body velocity. On a robot 0.105 m tall the jump is inside the noise.

So the clip's **jump window** is found -- from the crouch before its first take-off
to the settle after its last landing -- and inside it the two penalties are off and
three terms from `jumper.jump` (`tasks/jumper/jump/mdp/rewards.py`) pay for the jump:
base height, base vertical velocity, and the support feet's contact state against
the clip's schedule. Outside the window the task is exactly `janken_env_cfg`'s, so
the rest of the take keeps what `jumper.janken_win_hop` learned to do with it.

Mechanism only: every weight, kernel width and threshold is a required argument of
`janken_jump_env_cfg`, stated by the task.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
import torch
from mjlab.managers.metrics_manager import MetricsTermCfg
from mjlab.managers.reward_manager import RewardTermCfg
from mjlab.managers.scene_entity_config import SceneEntityCfg
from mjlab.sensor import ContactMatch, ContactSensor, ContactSensorCfg
from mjlab.tasks.tracking.mdp.commands import MotionCommand

from .constants import FOOT_GEOMS, get_spec
from .dance.env import COMMAND
from .dance.motion import SUPPORT_LEGS
from .dance.rewards import actuator_power_cost, torque_headroom_cost
from .janken import janken_env_cfg

if TYPE_CHECKING:
    from mjlab.envs import ManagerBasedRlEnv

__all__ = [
    "JumpStats",
    "actuator_power_cost_outside",
    "janken_jump_env_cfg",
    "jump_base_height",
    "jump_base_vz",
    "jump_contact",
    "measure_jump",
    "support_feet_clearance",
    "torque_headroom_cost_outside",
]

#: The contact sensor on the four support feet's collision geoms.
SENSOR = "support_feet_ground"
SUPPORT_GEOMS: tuple[str, ...] = tuple(
    g for g in FOOT_GEOMS if g.split("_", 1)[0] in SUPPORT_LEGS
)

_DEFAULT_ASSET_CFG = SceneEntityCfg("robot")

Ranges = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class JumpStats:
    """What `measure_jump` finds, in the motion's control frames ([start, end))."""

    window: Ranges
    airborne: Ranges
    crouch_to_apex_m: float
    peak_vz: float
    #: The support feet's sites' height standing on the floor (they sit above the
    #: contact surface), so that height less this is clearance.
    site_floor_m: float


def _runs(mask: np.ndarray) -> Ranges:
    edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(np.int8), 0]))
    return tuple((int(a), int(b)) for a, b in zip(edges[::2], edges[1::2]))


def _rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate `v` [3] by the unit quaternions `q` [..., 4] (w, x, y, z)."""
    w, u = q[..., :1], q[..., 1:]
    t = 2.0 * np.cross(u, np.broadcast_to(v, u.shape))
    return v + w * t + np.cross(u, t)


def measure_jump(
    motion_npz: Path, asset: Path | None, clearance_m: float, lead_s: float, tail_s: float
) -> JumpStats:
    """Find the jump in a converted clip (`dance/motion.py`'s cache, at control rate).

    A support foot is off the floor when its site -- the point the converter's ground
    check measures (`_check_support_feet`) -- is more than `clearance_m` above the
    lowest it goes in the clip, where it stands. Body origins will not do: the foot
    tips' origins sit 11 mm from their sites and move by 5 mm through a crouch with
    the foot planted. The window is the airborne frames widened by `lead_s` before
    and `tail_s` after, merged where they meet.
    """
    model = get_spec(asset).compile()
    with np.load(motion_npz) as m:
        names = [str(n) for n in m["body_names"]]
        pos, quat, lin = m["body_pos_w"], m["body_quat_w"], m["body_lin_vel_w"]
        fps = float(m["fps"])
    z = []
    for leg in SUPPORT_LEGS:
        site = model.site(leg)
        b = names.index(model.body(int(site.bodyid[0])).name)
        z.append(pos[:, b, 2] + _rotate(quat[:, b], np.asarray(site.pos))[:, 2])
    site_z = np.stack(z, axis=1)
    clearance = site_z - site_z.min(axis=0)
    up = clearance > clearance_m
    if not up.all(axis=1).any():
        raise ValueError(
            f"{motion_npz.name}: the support feet never all leave the floor by "
            f"{clearance_m * 1000:.1f} mm, so there is no jump to reward."
        )
    if not np.array_equal(up.all(axis=1), up.any(axis=1)):
        raise ValueError(
            f"{motion_npz.name}: the support feet do not leave and land together "
            f"(any up {_runs(up.any(axis=1))}, all up {_runs(up.all(axis=1))}). "
            f"The contact term scores the clip's schedule as one state for all four."
        )
    airborne = up.all(axis=1)
    lead, tail = round(lead_s * fps), round(tail_s * fps)
    window = np.zeros_like(airborne)
    for a, b in _runs(airborne):
        window[max(a - lead, 0):min(b + tail, len(window))] = True
    base = names.index("base_link")
    inside = np.flatnonzero(window)
    zb = pos[inside, base, 2]
    return JumpStats(
        window=_runs(window),
        airborne=_runs(airborne),
        crouch_to_apex_m=float(zb.max() - zb.min()),
        peak_vz=float(np.abs(lin[inside, base, 2]).max()),
        site_floor_m=float(site_z.min()),
    )


def _motion(env: ManagerBasedRlEnv, command_name: str) -> MotionCommand:
    return cast(MotionCommand, env.command_manager.get_term(command_name))


def _in(env: ManagerBasedRlEnv, command_name: str, ranges: Ranges) -> torch.Tensor:
    """1.0 where the command's current frame is inside one of `ranges`, [num_envs].
    The per-frame table is built once per (command, ranges) and kept on the env."""
    command = _motion(env, command_name)
    tables = env.__dict__.setdefault("_janken_jump_tables", {})
    key = (command_name, ranges)
    if key not in tables:
        table = torch.zeros(command.motion.time_step_total, device=env.device)
        for a, b in ranges:
            table[a:b] = 1.0
        tables[key] = table
    return tables[key][command.time_steps]


def actuator_power_cost_outside(
    env: ManagerBasedRlEnv,
    command_name: str,
    window: Ranges,
    asset_cfg: SceneEntityCfg = _DEFAULT_ASSET_CFG,
) -> torch.Tensor:
    """`actuator_power_cost`, zero inside the jump window."""
    return actuator_power_cost(env, asset_cfg) * (1.0 - _in(env, command_name, window))


def torque_headroom_cost_outside(
    env: ManagerBasedRlEnv,
    command_name: str,
    window: Ranges,
    asset_cfg: SceneEntityCfg = _DEFAULT_ASSET_CFG,
) -> torch.Tensor:
    """`torque_headroom_cost`, zero inside the jump window."""
    return torque_headroom_cost(env, asset_cfg) * (1.0 - _in(env, command_name, window))


def jump_base_height(
    env: ManagerBasedRlEnv, command_name: str, window: Ranges, sigma_sq: float
) -> torch.Tensor:
    """`jumper.jump`'s `ref_base_height` inside the window: exp(-dz^2 / sigma_sq)."""
    c = _motion(env, command_name)
    e = (c.robot_anchor_pos_w[:, 2] - c.anchor_pos_w[:, 2]) ** 2
    return torch.exp(-e / sigma_sq) * _in(env, command_name, window)


def jump_base_vz(
    env: ManagerBasedRlEnv, command_name: str, window: Ranges, sigma_sq: float
) -> torch.Tensor:
    """`jumper.jump`'s `ref_base_lin_vel` inside the window, on the vertical alone:
    rising slowly to the right height is not a jump. The horizontal part is already
    mjlab's `motion_body_lin_vel`'s."""
    c = _motion(env, command_name)
    e = (c.robot_anchor_lin_vel_w[:, 2] - c.anchor_lin_vel_w[:, 2]) ** 2
    return torch.exp(-e / sigma_sq) * _in(env, command_name, window)


def _in_contact(env: ManagerBasedRlEnv, sensor_name: str, force_threshold: float):
    sensor: ContactSensor = env.scene[sensor_name]
    force = sensor.data.force
    assert force is not None
    return force.norm(dim=-1) > force_threshold


def jump_contact(
    env: ManagerBasedRlEnv,
    command_name: str,
    window: Ranges,
    airborne: Ranges,
    sensor_name: str,
    force_threshold: float,
) -> torch.Tensor:
    """`jumper.jump`'s `ref_contact` inside the window: the fraction of support feet
    whose contact state is the clip's. When the feet leave and land is the jump, and
    pose tracking is nearly blind to a take-off a step late; this is the term that
    says so. The clip's four feet share one state (`measure_jump` checks), so the
    sensor's order of them does not matter."""
    planted = 1.0 - _in(env, command_name, airborne)
    match = _in_contact(env, sensor_name, force_threshold).float() == planted[:, None]
    return match.float().mean(dim=1) * _in(env, command_name, window)


def support_feet_clearance(env: ManagerBasedRlEnv, floor_m: float) -> torch.Tensor:
    """How far the lowest of the four support feet is off the floor, in metres: the
    lowest site's height less `floor_m`, where the sites sit standing. A metric,
    reduced to its maximum over an episode -- how high the robot got all four feet.
    Not a count of steps without contact: `jumper.janken_win_hop`'s bounce breaks
    contact for 8 steps where the clip flies for 15, while its feet clear 4 mm to
    the clip's 33.6."""
    robot = env.scene["robot"]
    if not hasattr(env, "_janken_jump_sites"):
        ids, _ = robot.find_sites(list(SUPPORT_LEGS), preserve_order=True)
        env._janken_jump_sites = robot.indexing.site_ids[ids]
    # `site_xpos` rather than `EntityData.site_pos_w`: that one goes through the
    # site's full pose, and `site_xmat` is [..., 9] on the native backend where
    # `quat_from_matrix` wants [..., 3, 3], so it raises there.
    z = robot.data.data.site_xpos[:, env._janken_jump_sites, 2]
    return z.min(dim=1).values - env.scene.env_origins[:, 2] - floor_m


def janken_jump_env_cfg(
    media: Path,
    asset: Path | None,
    play: bool,
    *,
    clearance_m: float,
    lead_s: float,
    tail_s: float,
    height_sigma_ratio: float,
    vz_sigma_ratio: float,
    height_weight: float,
    vz_weight: float,
    contact_weight: float,
    contact_force_n: float,
):
    """`janken_env_cfg` with the jump window's terms. The kernel widths are given
    as fractions of the clip's own amplitude inside the window -- its crouch-to-apex
    height and its peak vertical speed -- as `jumper.jump` derives its own."""
    cfg = janken_env_cfg(media, asset, play)
    s = measure_jump(Path(cfg.commands[COMMAND].motion_file), asset,
                     clearance_m, lead_s, tail_s)

    cfg.scene.sensors = (cfg.scene.sensors or ()) + (
        ContactSensorCfg(
            name=SENSOR,
            primary=ContactMatch(mode="geom", pattern=SUPPORT_GEOMS, entity="robot"),
            secondary=ContactMatch(mode="body", pattern="terrain"),
            fields=("found", "force"),
            reduce="netforce",
            num_slots=1,
        ),
    )

    gate = {"command_name": COMMAND, "window": s.window}
    cfg.rewards["power"].func = actuator_power_cost_outside
    cfg.rewards["power"].params.update(gate)
    cfg.rewards["torque_headroom"].func = torque_headroom_cost_outside
    cfg.rewards["torque_headroom"].params.update(gate)

    cfg.rewards["jump_base_height"] = RewardTermCfg(
        func=jump_base_height, weight=height_weight,
        params={**gate, "sigma_sq": (height_sigma_ratio * s.crouch_to_apex_m) ** 2},
    )
    cfg.rewards["jump_base_vz"] = RewardTermCfg(
        func=jump_base_vz, weight=vz_weight,
        params={**gate, "sigma_sq": (vz_sigma_ratio * s.peak_vz) ** 2},
    )
    cfg.rewards["jump_contact"] = RewardTermCfg(
        func=jump_contact, weight=contact_weight,
        params={**gate, "airborne": s.airborne, "sensor_name": SENSOR,
                "force_threshold": contact_force_n},
    )
    cfg.metrics["feet_clearance"] = MetricsTermCfg(
        func=support_feet_clearance, reduce="max", params={"floor_m": s.site_floor_m},
    )
    return cfg

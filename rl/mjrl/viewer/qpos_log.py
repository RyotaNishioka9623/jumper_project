"""`play.py --qpos-out`: the replayed environment's full state, one row per control step.

The MP4 recorder (`video.py`) keeps the picture; this keeps what the picture was
drawn from -- `qpos` of one environment after every control step -- so a replay can
be rendered again elsewhere (scissors_crab/blender/import_rollout.py renders it in
Blender, with the face displays and props the simulator does not draw).

The file is an `.npz`:

    qpos           [T + 1, nq] float32, row 0 before the first step
    dt             control period, seconds
    joint_names    every joint in the compiled model, as MuJoCo names them
    joint_qposadr  where each one's coordinates start in a `qpos` row
    joint_type     MuJoCo's mjtJoint per joint (0 free, 3 hinge, ...)

Names are written as the compiled model has them, entity prefix included; a reader
matches them by suffix rather than this module guessing a prefix for it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


class QposLog:
    def __init__(self, env, path: Path, env_index: int = 0) -> None:
        self._env = env
        self.path = Path(path)
        self._index = env_index
        model = env.sim.mj_model
        self._names = np.array([model.joint(i).name for i in range(model.njnt)])
        self._adr = np.asarray(model.jnt_qposadr).copy()
        self._type = np.asarray(model.jnt_type).copy()
        self._dt = float(env.step_dt)
        self._rows = [self._row()]

    def _row(self) -> np.ndarray:
        return self._env.sim.data.qpos[self._index].detach().cpu().numpy().astype(np.float32)

    def update(self) -> None:
        """Record the state after one completed control step."""
        self._rows.append(self._row())

    @property
    def steps(self) -> int:
        return len(self._rows) - 1

    def close(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            self.path, qpos=np.stack(self._rows), dt=np.array(self._dt),
            joint_names=self._names, joint_qposadr=self._adr, joint_type=self._type,
        )

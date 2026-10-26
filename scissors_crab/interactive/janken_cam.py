#!/usr/bin/env python3
"""Play rock-paper-scissors against the crab: a camera reads your hand, the trained
policies answer in simulation.

    .venv/bin/python scissors_crab/interactive/janken_cam.py
    .venv/bin/python scissors_crab/interactive/janken_cam.py --record demo.mp4

Space starts a round. The crab warms up, calls "jan, ken" with its fist, and on "pon"
throws -- scissors, the only thing it can throw -- and holds it while it looks at
yours. Your hand just after the beat (by default the majority over 0.2-0.5 s after
"pon": on the beat itself most hands are still on the way), read by MediaPipe's
gesture recognizer from the Mac's camera, decides what happens next:

- rock: the crab loses and cries (`jumper.janken_lose`),
- paper: it wins, jumps and hides its face (`jumper.janken_win_jump`),
- scissors, or no hand seen: a draw, "aiko de sho", and you throw again on every
  "sho" until someone wins (`jumper.janken_draw`, its last cycle looped).

All three are the trained policies running live, one environment each, in this
process. On "pon" (and on each "sho") the active environment hands its physical state
-- qpos, qvel and the last actions -- to the one for the outcome, set to the same
point of its own clip: the clips share their opening frame for frame, so the crab
carries on from where it is rather than jumping to a recording. The face is the
take's eye animation (`tools/make_eyes.py`), shown where the robot shows it: on two
round screens on its face panel, placed as `blender/build_rig.py` places them.

Keys: space starts a round; r / p / s force rock / paper / scissors for one throw
(no camera needed); q or Esc quits. `--no-camera` runs on the keys alone and
`--script` drives a run unattended (for checking without a person in front of it).
"""

from __future__ import annotations

import argparse
import collections
import importlib
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
RENDERS = REPO / "scissors_crab" / "renders"
FONT = REPO / "scissors_crab/external/fonts/mplus-rounded-1c/MPLUSRounded1c-ExtraBold.ttf"
MODEL = REPO / "scissors_crab/external/models/gesture_recognizer.task"

#: The three outcomes: task, checkpoint, eye animation (the trained takes the video
#: was rendered from; AGENTS.md has where each came from).
TAKES = {
    "lose": ("jumper.janken_lose", "janken_lose/1fb58d6/model_1499.pt",
             "janken_lose/1fb58d6/eyes"),
    "win": ("jumper.janken_win_jump", "janken_win_jump/a1f8d50/model_3999.pt",
            "janken_win_jump/a1f8d50/eyes"),
    "draw": ("jumper.janken_draw", "janken_draw/97f28f8/model_1499.pt",
             "janken_draw/97f28f8/eyes"),
}

# ── The choreography's beats, in control steps (50 Hz) ───────────────────────
# Render frame f (30 fps, from 1) is t = (f - 1) / 30 s, control step 50 t. The
# beats are `motions/janken_common.opening()`'s and `make_janken_draw.py`'s plus the
# converter's 12-frame lead-in -- the frames stage.py and the edit use.
CONTROL_HZ = 50
EYE_FPS = 30


def step_of(render_frame: int) -> int:
    return round((render_frame - 1) / 30 * CONTROL_HZ)


START = step_of(61)        # mid warm-up: two snips, then the fist
JAN, KEN, PON = step_of(96), step_of(108), step_of(120)
#: When the hand is read, in seconds after the throw beat ("pon", "sho"): the
#: majority sign over [READ_FROM_S, DECIDE_AT_S], the outcome taken at the end. On
#: the beat itself most people's hands are still on the way, so the window starts
#: after it (both are options).
READ_FROM_S = 0.2
DECIDE_AT_S = 0.5
#: While the hand is being read the crab holds its throw: the clip is held on a step
#: of the still scissors after the beat. Every clip is still from "pon" (198) to step
#: 204, and the three agree through 211; the draw's "sho" is still for 19 steps.
PON_HOLD = PON + 4
SHO_HOLD = 16
#: The draw's "aiko de sho" cycles: cycle i starts on render frame 138 + 36 i,
#: throws ("sho") on 162 + 36 i and ends on 174 + 36 i; there are three. The last
#: one is looped, its seam measured under a degree (AGENTS.md).
CYCLE = 60  # 36 render frames
AIKO = [step_of(138) + CYCLE * i for i in range(3)]
SHO = [step_of(162) + CYCLE * i for i in range(3)]
LOOP_END = step_of(174) + CYCLE * 2

SIGNS = ("rock", "paper", "scissors")
OUTCOME = {"rock": "lose", "paper": "win", "scissors": "draw", None: "draw"}
SIGN_TEXT = {"rock": ("グー", "Rock"), "paper": ("パー", "Paper"),
             "scissors": ("チョキ", "Scissors"), None: ("？", "No hand")}
RESULT_TEXT = {"lose": ("カニの負け…", "The crab loses..."),
               "win": ("カニの勝ち！", "The crab wins!"),
               "draw": ("あいこ！", "Draw!")}


# ── The crab: three trained policies, one environment each ───────────────────

#: The face: two round 0.9-inch screens on the display module's front panel --
#: `blender/build_rig.py`'s numbers (the panel's outward normal and the centre of its
#: front face in the base frame, the eyes' radius and spacing).
PANEL_NORMAL = np.array((0.8, 0.0, 0.6))
PANEL_CENTRE = np.array((0.0764, 0.0, 0.0541))
EYE_RADIUS = 0.0229 / 2
EYE_SPACING = 0.052


def render_model(eye_px: int):
    """The robot for drawing: jumper.xml on a light floor, lit as
    `tools/preview_clip.py` lights it, with each eye a textured disc on the face
    panel (`eye_R` at -y, the robot's right, drawn for the viewer's left)."""
    import mujoco

    spec = mujoco.MjSpec.from_file(str(REPO / "assets" / "jumper" / "jumper.xml"))
    tex = spec.add_texture(name="grid", type=mujoco.mjtTexture.mjTEXTURE_2D,
                           builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                           rgb1=[0.82, 0.82, 0.80], rgb2=[0.74, 0.74, 0.72],
                           width=512, height=512)
    mat = spec.add_material(name="grid", texrepeat=[8, 8], reflectance=0.05)
    mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = tex.name
    spec.worldbody.add_geom(type=mujoco.mjtGeom.mjGEOM_PLANE, size=[3, 3, 0.1],
                            material="grid")
    directional = mujoco.mjtLightType.mjLIGHT_DIRECTIONAL
    spec.worldbody.add_light(type=directional, pos=[2, -2, 3], dir=[-0.5, 0.5, -1],
                             diffuse=[0.7] * 3, castshadow=True)
    spec.worldbody.add_light(type=directional, pos=[-2, 2, 2], dir=[0.5, -0.5, -1],
                             diffuse=[0.3] * 3, castshadow=False)
    spec.visual.headlight.ambient = [0.35] * 3
    spec.visual.headlight.diffuse = [0.35] * 3
    # A pale sky rather than MuJoCo's black past the floor's edge.
    spec.add_texture(name="sky", type=mujoco.mjtTexture.mjTEXTURE_SKYBOX,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT,
                     rgb1=[0.93, 0.94, 0.96], rgb2=[0.80, 0.84, 0.89], width=256, height=1536)

    n = PANEL_NORMAL / np.linalg.norm(PANEL_NORMAL)
    up = np.array((0.0, 0.0, 1.0)) - n * n[2]
    up /= np.linalg.norm(up)
    across = np.array((0.0, 1.0, 0.0))  # the picture's x: to the viewer's right
    seg = 48
    base = spec.body("base_link")
    for side, y in (("R", -EYE_SPACING / 2), ("L", EYE_SPACING / 2)):
        centre = PANEL_CENTRE + np.array((0.0, y, 0.0)) + n * 0.0008
        verts, uvs = [centre], [(0.5, 0.5)]
        for i in range(seg):
            a = 2 * math.pi * i / seg
            verts.append(centre + EYE_RADIUS * (math.cos(a) * across + math.sin(a) * up))
            uvs.append((0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)))
        spec.add_mesh(name=f"eye_{side}", uservert=np.ravel(verts).tolist(),
                      userface=[v for i in range(seg) for v in (0, 1 + i, 1 + (i + 1) % seg)],
                      usertexcoord=np.ravel(uvs).tolist(),
                      inertia=mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL)
        screen = spec.add_texture(name=f"eye_{side}", type=mujoco.mjtTexture.mjTEXTURE_2D,
                                  builtin=mujoco.mjtBuiltin.mjBUILTIN_FLAT, rgb1=[0, 0, 0],
                                  width=eye_px, height=eye_px)
        glow = spec.add_material(name=f"eye_{side}", emission=1.0, specular=0.0,
                                 shininess=0.0)
        glow.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = screen.name
        base.add_geom(type=mujoco.mjtGeom.mjGEOM_MESH, meshname=f"eye_{side}",
                      material=f"eye_{side}", contype=0, conaffinity=0, group=1, mass=0)
    return spec.compile()


@dataclass
class Take:
    name: str
    env: object
    wrapped: object
    policy: object
    obs: object = None

    @property
    def command(self):
        return self.env.command_manager.get_term("motion")

    @property
    def step(self) -> int:
        return int(self.command.time_steps[0])

    @property
    def length(self) -> int:
        return int(self.command.motion.time_step_total)


class Crab:
    """The live simulation: whichever take is active steps at 50 Hz."""

    def __init__(self, render_size: tuple[int, int], eye_px: int) -> None:
        import mujoco
        import torch

        sys.path.insert(0, str(REPO))
        resolve = importlib.import_module("mjrl.backend.resolve")
        from mjrl.backend.select import use_backend

        # Before any environment is built (CLAUDE.md, "The seam is one swapped class").
        use_backend(resolve.resolve(backend="native", device="cpu", num_envs=1,
                                    training=False))
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.rl import RslRlVecEnvWrapper
        from mjlab.rl.runner import MjlabOnPolicyRunner
        from mjrl.replay import skip_rewards

        import tasks

        self.torch = torch
        self.takes: dict[str, Take] = {}
        for name, (task_id, ckpt, _) in TAKES.items():
            cfg = tasks.load_env_cfg(task_id, play=True)
            cfg.scene.num_envs = 1
            # The dToF is the replay viewer's (2268 rays a step); nothing here reads it.
            cfg.scene.sensors = tuple(s for s in (cfg.scene.sensors or ()) if s.name != "tof")
            agent_cfg = tasks.load_agent_cfg(task_id)
            env = ManagerBasedRlEnv(cfg=cfg, device="cpu")
            skip_rewards(env)
            wrapped = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
            runner_cls = tasks.load_runner_cls(task_id) or MjlabOnPolicyRunner
            runner = runner_cls(wrapped, asdict(agent_cfg), device="cpu")
            runner.load(str(RENDERS / ckpt), load_cfg={"actor": True}, strict=True,
                        map_location="cpu")
            self.takes[name] = Take(name, env, wrapped, runner.get_inference_policy("cpu"))
            print(f"[crab] {name}: {task_id} <- {ckpt}")
        self.active = self.takes["lose"]

        self.mujoco = mujoco
        self.model = render_model(eye_px)
        self.data = mujoco.MjData(self.model)
        w, h = render_size
        self.model.vis.global_.offwidth = max(self.model.vis.global_.offwidth, w)
        self.model.vis.global_.offheight = max(self.model.vis.global_.offheight, h)
        self.renderer = mujoco.Renderer(self.model, height=h, width=w)
        # The simulation's scene names the robot's joints "robot/<name>": copy qpos
        # across by name rather than trusting the two layouts to agree.
        sim_model = self.active.env.sim.mj_model
        width = {mujoco.mjtJoint.mjJNT_FREE: 7, mujoco.mjtJoint.mjJNT_BALL: 4}
        src, dst = [], []
        for j in range(self.model.njnt):
            name = self.model.joint(j).name
            k = mujoco.mj_name2id(sim_model, mujoco.mjtObj.mjOBJ_JOINT, f"robot/{name}")
            if k < 0:
                raise RuntimeError(f"the simulation has no joint robot/{name}")
            nq = width.get(self.model.jnt_type[j], 1)
            dst += range(self.model.jnt_qposadr[j], self.model.jnt_qposadr[j] + nq)
            src += range(sim_model.jnt_qposadr[k], sim_model.jnt_qposadr[k] + nq)
        self.qpos_from, self.qpos_to = np.array(src), np.array(dst)
        self.screens = [self.model.texture(f"eye_{side}").id for side in ("R", "L")]
        self.camera = mujoco.MjvCamera()
        self.camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        # The player's view: in front of the crab (it faces +X), a little to its left.
        self.camera.azimuth, self.camera.elevation, self.camera.distance = 200.0, -16.0, 0.56

    def start(self, step: int) -> None:
        """A round: the lose take (any would do, they share the opening) placed on its
        own clip's reference at `step`."""
        t = self.takes["lose"]
        t.wrapped.reset()
        cmd = t.command
        cmd.time_steps[:] = step
        ids = self.torch.arange(t.env.num_envs)
        cmd._write_reference_state_to_sim(
            ids, cmd.body_pos_w[:, 0].clone(), cmd.body_quat_w[:, 0].clone(),
            cmd.body_lin_vel_w[:, 0].clone(), cmd.body_ang_vel_w[:, 0].clone(),
            cmd.joint_pos.clone(), cmd.joint_vel.clone())
        t.env.sim.forward()
        cmd.update_relative_body_poses()
        t.obs = t.wrapped.get_observations()
        self.active = t

    def hand_over(self, name: str, step: int) -> None:
        """Continue as take `name` from the active take's physical state, at `step`
        of `name`'s clip."""
        src, dst = self.active, self.takes[name]
        if dst is not src:
            dst.wrapped.reset()
            dst.env.sim.data.qpos[:] = src.env.sim.data.qpos
            dst.env.sim.data.qvel[:] = src.env.sim.data.qvel
            sa, da = src.env.action_manager, dst.env.action_manager
            da._action[:] = sa._action
            da._prev_action[:] = sa._prev_action
            da._prev_prev_action[:] = sa._prev_prev_action
        dst.command.time_steps[:] = step
        dst.env.sim.forward()
        dst.command.update_relative_body_poses()
        dst.obs = dst.wrapped.get_observations()
        self.active = dst

    def advance(self) -> bool:
        """One control step of the active take. False if it fell or ran out."""
        t = self.active
        if t.step >= t.length - 2:
            return False
        t.obs, _, dones, _ = t.wrapped.step(t.policy(t.obs))
        return not bool(dones[0])

    def render(self, eyes: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
        """The crab as it is now, with `eyes` (right, left: RGB, rows bottom-up, as
        `load_eyes` gives them) on its screens."""
        _, live = self.active.env.sim.env_mjdata(0)
        self.data.qpos[self.qpos_to] = live.qpos[self.qpos_from]
        self.mujoco.mj_forward(self.model, self.data)
        for tex, img in zip(self.screens, eyes):
            adr = self.model.tex_adr[tex]
            self.model.tex_data[adr:adr + img.size] = img.ravel()
            self.mujoco.mjr_uploadTexture(self.model, self.renderer._mjr_context, tex)
        base = self.data.qpos[:3]
        self.camera.lookat[:] = (base[0] + 0.02, base[1], 0.095)
        self.renderer.update_scene(self.data, camera=self.camera)
        return self.renderer.render()


# ── The hand ──────────────────────────────────────────────────────────────────

#: MediaPipe's 21-point hand: the four fingers' (mcp, pip, tip) and the bones drawn.
FINGERS = {"index": (5, 6, 8), "middle": (9, 10, 12), "ring": (13, 14, 16),
           "pinky": (17, 18, 20)}
BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9),
         (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17),
         (17, 18), (18, 19), (19, 20), (0, 17)]
#: The recognizer's own gestures for the three throws.
GESTURES = {"Closed_Fist": "rock", "Open_Palm": "paper", "Victory": "scissors"}


def classify(points: np.ndarray) -> str | None:
    """Rock, paper or scissors from the 21 landmarks [21, 3], by which of the four
    fingers are straight: a finger is out when its tip is past its middle joint and
    the two segments either side of that joint are within ~45 degrees of a line.
    The thumb is left out -- it folds across a fist and sticks out of a V either way."""
    wrist = points[0]
    out = {}
    for name, (mcp, pip, tip) in FINGERS.items():
        a, b = points[pip] - points[mcp], points[tip] - points[pip]
        cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        reach = np.linalg.norm(points[tip] - wrist) > np.linalg.norm(points[pip] - wrist)
        out[name] = cos > 0.7 and reach
    n = sum(out.values())
    if n == 0:
        return "rock"
    if out["index"] and out["middle"] and not out["ring"] and not out["pinky"]:
        return "scissors"
    if n >= 3 and (out["ring"] or out["pinky"]):
        return "paper"
    return None


class Hand:
    """MediaPipe's gesture recognizer on camera frames: the sign, held steady."""

    def __init__(self) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision

        if not MODEL.exists():
            raise SystemExit(f"error: {MODEL} is missing (README: the gesture model).")
        self.mp = mp
        self.recognizer = vision.GestureRecognizer.create_from_options(
            vision.GestureRecognizerOptions(
                base_options=mpt.BaseOptions(model_asset_path=str(MODEL)),
                running_mode=vision.RunningMode.VIDEO, num_hands=1))
        self.recent: collections.deque = collections.deque(maxlen=5)
        self.t0 = time.perf_counter()

    def read(self, bgr: np.ndarray) -> tuple[str | None, np.ndarray | None]:
        """(steady sign or None, landmarks [21, 3] in image fractions or None)."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        ms = int((time.perf_counter() - self.t0) * 1000)
        r = self.recognizer.recognize_for_video(image, ms)
        sign, points = None, None
        if r.hand_landmarks:
            points = np.array([(p.x, p.y, p.z) for p in r.hand_landmarks[0]])
            sign = classify(points)
            if sign is None and r.gestures:
                g = r.gestures[0][0]
                if g.score > 0.6:
                    sign = GESTURES.get(g.category_name)
        self.recent.append(sign)
        best, count = collections.Counter(self.recent).most_common(1)[0]
        return (best if count >= 3 else None), points


# ── The game ──────────────────────────────────────────────────────────────────

@dataclass
class Throw:
    """A beat on which the player throws: `beat` and `hold` are steps of the active
    clip; `clock` is the game clock (ticks) when the beat came, None until it has."""

    beat: int
    hold: int
    clock: int | None = None


class Game:
    """Idle -> opening -> (throw) -> reaction, or draw -> (throw on each sho) -> ..."""

    def __init__(self, crab: Crab, read_from_s: float = READ_FROM_S,
                 decide_at_s: float = DECIDE_AT_S) -> None:
        if not 0.0 <= read_from_s < decide_at_s:
            raise ValueError("the hand must be read from before the decision")
        self.crab = crab
        self.read_from = round(read_from_s * CONTROL_HZ)
        self.decide_at = round(decide_at_s * CONTROL_HZ)
        self.state = "idle"
        self.throw: Throw | None = None
        self.clock = 0
        self.signs: list[tuple[int, str | None]] = []  # (clock, sign)
        self.forced: str | None = None
        self.result: tuple[str, str | None, float] | None = None  # outcome, sign, time

    def start(self) -> None:
        self.crab.start(START)
        self.state, self.signs, self.result = "opening", [], None
        self.throw = Throw(PON, PON_HOLD)

    def tick(self, sign: str | None) -> None:
        """One control step with the hand as it is now."""
        if self.state == "idle":
            return
        self.clock += 1
        self.signs.append((self.clock, self.forced or sign))
        t = self.throw
        if t is not None:
            if t.clock is None and self.crab.active.step >= t.beat:
                t.clock = self.clock
            if t.clock is not None and self.clock >= t.clock + self.decide_at:
                self.decide()
        take, t = self.crab.active, self.throw
        if t is not None and t.clock is not None and take.step >= t.hold:
            # Hold the throw until the hand has been read.
            take.command.time_steps[:] = t.hold
        elif self.state == "draw" and take.step >= LOOP_END:
            # Round and round: back to the last cycle's start, the same pose (scissors).
            take.command.time_steps[:] = AIKO[2]
            self.throw = Throw(SHO[2], SHO[2] + SHO_HOLD)
        if not self.crab.advance():
            self.state = "idle"

    def decide(self) -> None:
        start = self.throw.clock + self.read_from
        thrown = [s for c, s in self.signs if c >= start and s]
        sign = collections.Counter(thrown).most_common(1)[0][0] if thrown else None
        outcome = OUTCOME[sign]
        self.result = (outcome, sign, time.perf_counter())
        self.forced, self.signs = None, []
        if outcome == "draw":
            if self.state != "draw":
                # The draw's clip, on the same still scissors after its own "pon".
                self.crab.hand_over("draw", PON_HOLD)
                self.state = "draw"
            k = self.crab.active.step
            # The next "sho"; past the last one, the loop in tick() sets it again.
            nxt = next((s for s in SHO if s > k), None)
            self.throw = Throw(nxt, nxt + SHO_HOLD) if nxt is not None else None
        else:
            # The reaction's own clip from the still scissors after "pon": the crab
            # held its throw while the hand was read, and reacts now.
            self.crab.hand_over(outcome, PON_HOLD)
            self.state, self.throw = "reaction", None

    def call(self) -> tuple[str, str] | None:
        """The caption for the beat the crab is on."""
        if self.state == "idle":
            return ("スペースキーでじゃんけん", "Press space to play")
        k, t = self.crab.active.step, self.throw
        if self.state == "opening":
            if JAN - 8 <= k < KEN - 8:
                return ("じゃん", "Rock,")
            if KEN - 8 <= k < PON - 8:
                return ("けん", "paper,")
            if k >= PON - 8:  # until the hand has been read
                return ("ぽん！", "scissors, shoot!")
        if self.state == "draw" and t is not None:
            if t.beat - 40 <= k < t.beat - 8:
                return ("あいこで", "Again...")
            if k >= t.beat - 8:
                return ("しょ！", "shoot!")
        return None


# ── Drawing ───────────────────────────────────────────────────────────────────

class Captions:
    def __init__(self) -> None:
        self.cache: dict = {}

    def get(self, text: str, sub: str | None, size: int) -> np.ndarray:
        key = (text, sub, size)
        if key not in self.cache:
            font = ImageFont.truetype(str(FONT), size)
            sub_font = ImageFont.truetype(str(FONT), max(14, int(size * 0.45)))
            lines = [(text, font, max(3, size // 10))]
            if sub:
                lines.append((sub, sub_font, max(2, size // 16)))
            boxes = [ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), t, font=f,
                                                                        stroke_width=s)
                     for t, f, s in lines]
            w = max(b[2] - b[0] for b in boxes) + 8
            h = sum(b[3] - b[1] for b in boxes) + 8 * len(lines)
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d, y = ImageDraw.Draw(img), 2
            for (t, f, s), b in zip(lines, boxes):
                x = (w - (b[2] - b[0])) // 2 - b[0]
                d.text((x, y - b[1]), t, font=f, fill=(255, 255, 255), stroke_width=s,
                       stroke_fill=(60, 40, 30))
                y += b[3] - b[1] + 8
            self.cache[key] = np.array(img)[:, :, [2, 1, 0, 3]]  # RGBA -> BGRA
        return self.cache[key]

    def put(self, frame: np.ndarray, text: str, sub: str | None, size: int,
            cx: int, cy: int) -> None:
        img = self.get(text, sub, size)
        h, w = img.shape[:2]
        x0, y0 = max(0, cx - w // 2), max(0, cy - h // 2)
        x1, y1 = min(frame.shape[1], x0 + w), min(frame.shape[0], y0 + h)
        tile = img[: y1 - y0, : x1 - x0]
        a = tile[:, :, 3:4] / 255.0
        frame[y0:y1, x0:x1] = (frame[y0:y1, x0:x1] * (1 - a) + tile[:, :, :3] * a).astype(
            np.uint8)


def load_eyes() -> dict[str, list[tuple[np.ndarray, np.ndarray]]]:
    eyes = {}
    for name, (_, _, path) in TAKES.items():
        d = RENDERS / path
        rs, ls = sorted((d / "R").glob("*.png")), sorted((d / "L").glob("*.png"))
        if not rs or len(rs) != len(ls):
            raise SystemExit(f"error: no eye frames in {d} (tools/make_eyes.py writes them)")
        # RGB with the rows bottom-up: a MuJoCo texture's first row is its bottom.
        eyes[name] = [tuple(np.ascontiguousarray(cv2.cvtColor(cv2.imread(str(f)),
                                                              cv2.COLOR_BGR2RGB)[::-1])
                            for f in pair) for pair in zip(rs, ls)]
    return eyes


def compose(cam: np.ndarray | None, points: np.ndarray | None, sign: str | None,
            crab_rgb: np.ndarray, game: Game, caps: Captions) -> np.ndarray:
    W, H = 1280, 720
    frame = np.full((H, W, 3), (236, 240, 244), np.uint8)
    # Left: the player, mirrored like a mirror.
    if cam is not None:
        view = cv2.resize(cam, (640, 480))
        if points is not None:
            px = [(int(x * 640), int(y * 480)) for x, y, _ in points]
            for a, b in BONES:
                cv2.line(view, px[a], px[b], (90, 230, 255), 2, cv2.LINE_AA)
            for p in px:
                cv2.circle(view, p, 3, (40, 80, 255), -1, cv2.LINE_AA)
        frame[120:600, 0:640] = cv2.flip(view, 1)
    else:
        frame[120:600, 0:640] = 200
        caps.put(frame, "カメラなし", "keys r / p / s", 40, 320, 360)
    # Right: the crab, its face on its own screens; and its throw, under it.
    frame[120:600, 640:1280] = cv2.cvtColor(crab_rgb, cv2.COLOR_RGB2BGR)
    caps.put(frame, "カニ：チョキ", "Crab: Scissors", 40, 960, 660)
    # Your sign, under you.
    ja, en = SIGN_TEXT[game.forced or sign]
    caps.put(frame, f"あなた：{ja}", en, 40, 320, 660)
    # The beat, or what happened, across the top.
    call = game.call()
    if game.result and time.perf_counter() - game.result[2] < 2.5 and (
            call is None or game.state == "reaction"):
        outcome, thrown, _ = game.result
        ja_t, en_t = SIGN_TEXT[thrown]
        ja_r, en_r = RESULT_TEXT[outcome]
        caps.put(frame, f"{ja_t} 対 チョキ → {ja_r}", f"{en_t} vs Scissors -> {en_r}", 52,
                 640, 60)
    elif call:
        caps.put(frame, call[0], call[1], 64, 640, 60)
    return frame


# ── Main loop ─────────────────────────────────────────────────────────────────

def parse_script(text: str | None) -> list[tuple[float, str]]:
    """"start@0.5,rock@3.9" -> [(0.5, "start"), (3.9, "rock")]"""
    if not text:
        return []
    out = []
    for item in text.split(","):
        what, _, at = item.partition("@")
        out.append((float(at), what.strip()))
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    ap.add_argument("--no-camera", action="store_true", help="keys only: r / p / s")
    ap.add_argument("--record", type=Path, help="also write the window to this .mp4")
    ap.add_argument("--headless", action="store_true", help="no window (with --script)")
    ap.add_argument("--script", help='timed inputs, e.g. "start@0.5,rock@3.9" (seconds)')
    ap.add_argument("--seconds", type=float, help="stop after this long")
    ap.add_argument("--read-from", type=float, default=READ_FROM_S, metavar="S",
                    help="read the hand from this long after pon / sho (default "
                         f"{READ_FROM_S})")
    ap.add_argument("--decide-at", type=float, default=DECIDE_AT_S, metavar="S",
                    help=f"and decide this long after it (default {DECIDE_AT_S})")
    args = ap.parse_args(argv)

    print("[janken] building the three crabs (takes a little while)...")
    eyes = load_eyes()
    crab = Crab((640, 480), eyes["lose"][0][0].shape[0])
    game = Game(crab, args.read_from, args.decide_at)
    caps = Captions()
    hand = None if args.no_camera else Hand()
    cap = None
    if hand is not None:
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            raise SystemExit("error: the camera did not open. On macOS, allow camera "
                             "access for this terminal app (System Settings > Privacy & "
                             "Security > Camera), then run again; or use --no-camera.")
    writer = None
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(args.record), cv2.VideoWriter_fourcc(*"mp4v"), 30,
                                 (1280, 720))
    script = parse_script(args.script)
    crab_rgb = crab.render(eyes["lose"][0])

    print("[janken] ready: space = play, r / p / s = force a throw, q = quit")
    t0 = time.perf_counter()
    sim_t = t0  # wall time the simulation has reached
    next_frame = t0
    next_rec = t0  # the recording keeps wall-clock time: a slow frame is written twice
    cam_bgr = points = None
    sign = None
    # Everything after building runs without autograd: tensors the steps create are
    # inference tensors, and the next round writes into them in place.
    try:
        with crab.torch.inference_mode():
            while True:
                now = time.perf_counter()
                if args.seconds and now - t0 > args.seconds:
                    break
                while script and now - t0 >= script[0][0]:
                    what = script.pop(0)[1]
                    if what == "start":
                        game.start()
                        sim_t = now
                    elif what in SIGNS or what == "none":
                        game.forced = None if what == "none" else what
                if cap is not None:
                    ok, cam_bgr = cap.read()
                    if ok:
                        sign, points = hand.read(cam_bgr)
                    else:
                        cam_bgr = None
                elif now < next_frame:
                    time.sleep(next_frame - now)
                next_frame = max(next_frame + 1 / 30, time.perf_counter())
                # The simulation keeps wall-clock pace, 50 steps a second.
                now = time.perf_counter()
                if game.state == "idle":
                    sim_t = now
                n = 0
                while sim_t + 1 / CONTROL_HZ <= now and n < 10:
                    game.tick(sign)
                    sim_t += 1 / CONTROL_HZ
                    n += 1
                take = crab.active
                seq = eyes[take.name]
                i = min(int(take.step / CONTROL_HZ * EYE_FPS), len(seq) - 1)
                if n or game.state != "idle":
                    crab_rgb = crab.render(seq[i])
                frame = compose(cam_bgr, points, sign, crab_rgb, game, caps)
                while writer is not None and next_rec <= time.perf_counter():
                    writer.write(frame)
                    next_rec += 1 / 30
                if not args.headless:
                    cv2.imshow("Scissors Crab - janken", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break
                    if key == ord(" ") and game.state == "idle":
                        game.start()
                        sim_t = time.perf_counter()
                    for k, s in ((ord("r"), "rock"), (ord("p"), "paper"), (ord("s"), "scissors")):
                        if key == k:
                            game.forced = s
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()
            print(f"[janken] recorded {args.record}")
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())

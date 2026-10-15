#!/usr/bin/env python3
"""Play rock-paper-scissors against the crab: a camera reads your hand, the trained
policies answer in simulation.

    .venv/bin/python scissors_crab/interactive/janken_cam.py
    .venv/bin/python scissors_crab/interactive/janken_cam.py --record demo.mp4

Space starts a round. The crab warms up, calls "jan, ken" with its fist, and on "pon"
throws -- scissors, the only thing it can throw. Your hand at that moment, read by
MediaPipe's gesture recognizer from the Mac's camera, decides what happens next:

- rock: the crab loses and cries (`jumper.janken_lose`),
- paper: it wins, jumps and hides its face (`jumper.janken_win_jump`),
- scissors, or no hand seen: a draw, "aiko de sho", and you throw again on every
  "sho" until someone wins (`jumper.janken_draw`, its last cycle looped).

All three are the trained policies running live, one environment each, in this
process. On "pon" (and on each "sho") the active environment hands its physical state
-- qpos, qvel and the last actions -- to the one for the outcome, set to the same
point of its own clip: the clips share their opening frame for frame, so the crab
carries on from where it is rather than jumping to a recording. The face is the
take's eye animation (`tools/make_eyes.py`), shown beside the render the way the
robot shows it, on two round screens.

Keys: space starts a round; r / p / s force rock / paper / scissors for one throw
(no camera needed); q or Esc quits. `--no-camera` runs on the keys alone and
`--script` drives a run unattended (for checking without a person in front of it).
"""

from __future__ import annotations

import argparse
import collections
import importlib
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
#: Steps after a throw beat at which the hand is read and the outcome taken: the
#: reactions start 4 render frames after "pon" (step 212), so this is before them.
DECIDE = 10
#: The hand is the majority sign over [throw - LOOK_BACK, throw + DECIDE] -- people
#: throw a little early or late.
LOOK_BACK = 8
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

    def __init__(self, render_size: tuple[int, int]) -> None:
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

        sim = self.active.env.sim
        self.mujoco = mujoco
        self.model = sim.render_model
        self.data = mujoco.MjData(self.model)
        self.model.vis.headlight.ambient[:] = 0.45
        self.model.vis.headlight.diffuse[:] = 0.55
        w, h = render_size
        self.model.vis.global_.offwidth = max(self.model.vis.global_.offwidth, w)
        self.model.vis.global_.offheight = max(self.model.vis.global_.offheight, h)
        self.renderer = mujoco.Renderer(self.model, height=h, width=w)
        self.camera = mujoco.MjvCamera()
        self.camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        # The player's view: in front of the crab (it faces +X), a little to its left.
        self.camera.azimuth, self.camera.elevation, self.camera.distance = 200.0, -18.0, 0.62

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

    def render(self) -> np.ndarray:
        _, live = self.active.env.sim.env_mjdata(0)
        self.data.qpos[:] = live.qpos
        self.mujoco.mj_forward(self.model, self.data)
        base = self.data.qpos[:3]
        self.camera.lookat[:] = (base[0] + 0.02, base[1], 0.075)
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

class Game:
    """Idle -> opening -> (throw) -> reaction, or draw -> (throw on each sho) -> ..."""

    def __init__(self, crab: Crab) -> None:
        self.crab = crab
        self.state = "idle"
        self.throw_at: int | None = None
        self.signs: list[tuple[int, str | None]] = []
        self.forced: str | None = None
        self.result: tuple[str, str | None, float] | None = None  # outcome, sign, time

    def start(self) -> None:
        self.crab.start(START)
        self.state, self.throw_at, self.signs, self.result = "opening", PON, [], None

    def tick(self, sign: str | None) -> None:
        """One control step with the hand as it is now."""
        if self.state == "idle":
            return
        self.signs.append((self.crab.active.step, self.forced or sign))
        if self.throw_at is not None and self.crab.active.step >= self.throw_at + DECIDE:
            self.decide()
        take = self.crab.active
        if self.state == "draw" and take.step >= LOOP_END:
            # Round and round: back to the last cycle's start, the same pose (scissors).
            take.command.time_steps[:] = AIKO[2]
            self.throw_at, self.signs = SHO[2], []
        if not self.crab.advance():
            self.state = "idle"

    def decide(self) -> None:
        thrown = [s for k, s in self.signs if k >= self.throw_at - LOOK_BACK and s]
        sign = collections.Counter(thrown).most_common(1)[0][0] if thrown else None
        outcome = OUTCOME[sign]
        self.result = (outcome, sign, time.perf_counter())
        self.forced, self.signs = None, []
        if outcome == "draw":
            if self.state != "draw":
                # The draw's clip at the same step: just after its own "pon".
                self.crab.hand_over("draw", self.crab.active.step)
                self.state = "draw"
            k = self.crab.active.step
            # The next "sho"; past the last one, the loop in tick() sets it again.
            self.throw_at = next((s for s in SHO if s > k), None)
        else:
            # The reactions' own clips, just after their "pon".
            self.crab.hand_over(outcome, PON + DECIDE)
            self.state, self.throw_at = "reaction", None

    def call(self) -> tuple[str, str] | None:
        """The caption for the beat the crab is on."""
        if self.state == "idle":
            return ("スペースキーでじゃんけん", "Press space to play")
        k = self.crab.active.step
        if self.state == "opening":
            if JAN - 8 <= k < KEN - 8:
                return ("じゃん", "Rock,")
            if KEN - 8 <= k < PON - 8:
                return ("けん", "paper,")
            if PON - 8 <= k < PON + 20:
                return ("ぽん！", "scissors, shoot!")
        if self.state == "draw" and self.throw_at is not None:
            if self.throw_at - 40 <= k < self.throw_at - 8:
                return ("あいこで", "Again...")
            if self.throw_at - 8 <= k < self.throw_at + 20:
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
        eyes[name] = [(cv2.imread(str(r)), cv2.imread(str(l))) for r, l in zip(rs, ls)]
    return eyes


def round_screen(img: np.ndarray, size: int) -> np.ndarray:
    """An eye image on a round screen with a dark bezel, BGR [size, size]."""
    out = np.full((size, size, 3), 30, np.uint8)
    inner = int(size * 0.86)
    face = cv2.resize(img, (inner, inner), interpolation=cv2.INTER_AREA)
    o = (size - inner) // 2
    mask = np.zeros((inner, inner), np.uint8)
    cv2.circle(mask, (inner // 2, inner // 2), inner // 2, 255, -1)
    region = out[o:o + inner, o:o + inner]
    region[mask > 0] = face[mask > 0]
    cv2.circle(out, (size // 2, size // 2), size // 2 - 1, (70, 70, 70), 2)
    return out


def compose(cam: np.ndarray | None, points: np.ndarray | None, sign: str | None,
            crab_rgb: np.ndarray, eyes: tuple[np.ndarray, np.ndarray], game: Game,
            caps: Captions) -> np.ndarray:
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
    # Right: the crab, and its two screens under it.
    frame[120:600, 640:1280] = cv2.cvtColor(crab_rgb, cv2.COLOR_RGB2BGR)
    # The robot's right screen is on the viewer's left, as you face it.
    r, l = eyes
    frame[606:714, 850:958] = round_screen(r, 108)
    frame[606:714, 962:1070] = round_screen(l, 108)
    caps.put(frame, "カニの顔", "its two screens", 26, 1170, 660)
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
    args = ap.parse_args(argv)

    print("[janken] building the three crabs (takes a little while)...")
    crab = Crab((640, 480))
    game = Game(crab)
    eyes = load_eyes()
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
    crab_rgb = crab.render()

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
                if n:
                    crab_rgb = crab.render()
                take = crab.active
                seq = eyes[take.name]
                i = min(int(take.step / CONTROL_HZ * EYE_FPS), len(seq) - 1)
                frame = compose(cam_bgr, points, sign, crab_rgb, seq[i], game, caps)
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

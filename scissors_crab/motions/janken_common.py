"""What every janken clip shares: the poses, and the opening up to the scissors.

Imported by the `make_janken_*.py` scripts, which Blender runs against the rig. Every
outcome (lose, win, draw) plays the same opening, frame for frame, so the cut between
them in the edit is seamless; only what follows frame `OPENING_END` differs.

Joint values are radians. Arm joints J0, J2, J3 and J4 change sign between the left
and right claws, J1 does not; leg joints all change sign. Poses that move the body
were checked with the converter's resting-floor solver (`keyframes_to_npz.py`):
heights are the base's, against HOME's 106.5 mm.
"""

from __future__ import annotations

import bpy

J = {o["joint"]: o for o in bpy.data.objects if "joint" in o}
HOME = {n: o.rotation_euler[o["axis"]] for n, o in J.items()}

#: Four legs, leaning back as the official `gesture_hello` does at its peak (mirrored
#: onto the right claw), so a raised right claw does not tip the robot: 115 mm.
LEAN = {
    "LF_J0_joint": -0.5236, "LF_J1_joint": -0.8727, "LF_J2_joint": -0.6109,
    "LF_J3_joint": -1.5708,
    "LM_J0_joint": -0.4166, "LM_J1_joint": 0.248, "LM_J2_joint": -1.6407,
    "RM_J0_joint": 0.4175, "RM_J1_joint": -0.2489, "RM_J2_joint": 1.6439,
    "LR_J0_joint": 0.1694, "LR_J1_joint": 0.5996, "LR_J2_joint": -1.9041,
    "RR_J0_joint": -0.1698, "RR_J1_joint": -0.6012, "RR_J2_joint": 1.9079,
}

#: The right claw held up beside the face, closed, like a raised fist.
CLAW_UP = {"RF_J0_joint": 0.4, "RF_J1_joint": -2.9, "RF_J2_joint": 0.6, "RF_J3_joint": 0.6,
           "RF_J4_joint": 0.0}
#: Scissors: the claw turned toward the viewer and opened, a V. 1.5 rather than the
#: 1.6 stop keeps `RF_J4` inside its soft limit.
SCISSORS = {"RF_J0_joint": 0.6, "RF_J1_joint": -3.1, "RF_J2_joint": 0.5, "RF_J3_joint": 0.3,
            "RF_J4_joint": 1.5}
#: The claw folded in front of the face, closed: hiding.
COVER = {"RF_J0_joint": 0.5, "RF_J1_joint": -2.4, "RF_J2_joint": 1.2, "RF_J3_joint": 0.8,
         "RF_J4_joint": 0.0}


def mirror(arm: dict[str, float]) -> dict[str, float]:
    """A right-claw pose on the left claw: J1 keeps its sign, J0, J2, J3, J4 flip.

    With LEAN's four feet the left claw is free, so both claws can play: both covering
    the face (COVER and mirror(COVER)) leave the claws 4 mm apart and the robot on its
    four feet, checked against the collision geometry and the resting-floor solver."""
    return {k.replace("RF_", "LF_"): (v if "_J1_" in k else -v) for k, v in arm.items()}

#: The middle and rear legs' J1 moved together from LEAN (left by +d, right by -d):
#: +0.15 sinks to 104 mm, -0.25 rises to 130 mm, on the same four feet.
def legs_j1(d: float, d2: float = 0.0) -> dict[str, float]:
    """With `d2`, J2 moves too: +0.25/+0.20 crouches to 83 mm on the same four feet."""
    out = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        for leg in ("M", "R"):
            for j, delta in ((1, d), (2, d2)):
                name = f"{side}{leg}_J{j}_joint"
                out[name] = LEAN[name] + sign * delta
    return out


#: The last frame of the shared opening: "pon" lands 4 frames before it, and every
#: outcome reacts from here, at once -- the result is known at "pon".
OPENING_END = 112


ROOT = bpy.data.objects["jumper_root"]
G = 9.81


def hop(takeoff: int, landing: int) -> None:
    """Raise the root through a ballistic flight from `takeoff` to `landing`, keyed on
    every frame: the parabola g sets for that airtime (0.2 s rises 49 mm). Exported as
    `lift`, added to the solved height by the converter."""
    rest = ROOT["rest_z"]
    flight = (landing - takeoff) / 30.0
    v0 = G * flight / 2.0
    for f in range(takeoff, landing + 1):
        t = (f - takeoff) / 30.0
        ROOT.location.z = rest + max(0.0, v0 * t - G * t * t / 2.0)
        ROOT.keyframe_insert("location", index=2, frame=f)


def _fcurve(obj: bpy.types.Object, index: int):
    act = obj.animation_data.action
    fcurves = getattr(act, "fcurves", None)
    if fcurves is None:  # layered actions (Blender 4.4+): the first slot's channel bag
        fcurves = act.layers[0].strips[0].channelbag(act.slots[0]).fcurves
    return next(fc for fc in fcurves
                if fc.data_path == "rotation_euler" and fc.array_index == index)


def key(frame: int, *layers: dict[str, float], interp: str = "BEZIER") -> None:
    """Key the pose at `frame`. `interp` is the interpolation of the segment that starts
    here: "QUAD" (eased in, i.e. accelerating) for a push-off, BEZIER otherwise. It is
    set on the keyframe itself: the preference for new keys is not honoured by
    keyframe_insert in a background run."""
    pose = dict(HOME)
    for layer in layers:
        pose.update(layer)
    for name, obj in J.items():
        obj.rotation_euler[obj["axis"]] = pose[name]
        obj.keyframe_insert("rotation_euler", index=obj["axis"], frame=frame)
        # Set on every key: a new key takes its neighbour's interpolation otherwise.
        kp = next(k for k in _fcurve(obj, obj["axis"]).keyframe_points
                  if abs(k.co.x - frame) < 1e-6)
        kp.interpolation = interp
        kp.easing = "EASE_IN" if interp != "BEZIER" else "AUTO"


def opening(snips: bool = True) -> int:
    """HOME, ready, a practice swing of the scissors, then "jan", "ken", "pon".
    Returns the opening's last frame.

    The scissors are the joke, so they come first: raised as a V and snipped twice,
    slowly (0.6 s a snip), before the game -- the only move this crab has, warmed up.
    "Pon" then lands just before the end, and every outcome reacts at once. (Earlier
    cuts snipped after "pon" and only then reacted, as if the result came late.)

    Without `snips` (the draw: two crabs frozen on scissors is the joke there) the V is
    held still through the practice instead; the timing is the same either way."""
    for obj in J.values():
        obj.animation_data_clear()
    ROOT.animation_data_clear()
    ROOT.location.z = ROOT["rest_z"]
    key(1)
    # Practice: the V goes up, snip, snip.
    key(20, LEAN, SCISSORS)
    key(26, LEAN, SCISSORS)
    for f, j4 in ((35, 0.8), (44, 1.5), (53, 0.8), (62, 1.5)):
        key(f, LEAN, SCISSORS, {"RF_J4_joint": j4 if snips else SCISSORS["RF_J4_joint"]})
    key(66, LEAN, SCISSORS)
    # Ready for the game: the claw closes into a fist.
    key(76, LEAN, CLAW_UP)
    # jan, ken: down on the beat, back up between.
    for f, j1 in ((84, -2.5), (90, -3.0), (96, -2.5), (102, -3.0)):
        key(f, LEAN, CLAW_UP, {"RF_J1_joint": j1})
    # pon: scissors.
    key(108, LEAN, SCISSORS)
    key(OPENING_END, LEAN, SCISSORS)
    return OPENING_END


def set_down(frame: int) -> int:
    """From any LEAN pose at `frame`, back to HOME without the claws striking first:
    the claws come down to their HOME angles while the legs still lean (the body is
    tilted back, so they hover), then the legs settle and the claws meet the floor last.
    Going straight there let the claws reach the floor before the legs and tipped the
    body 15 degrees forward in one step. Returns the last frame."""
    legs = {k: v for k, v in LEAN.items() if not k.startswith("LF_")}
    key(frame + 14, legs)
    key(frame + 34)
    return frame + 34


def save(path, last_frame: int) -> None:
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, last_frame
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print(f"saved {path}")

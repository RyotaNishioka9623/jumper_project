#!/usr/bin/env python3
"""Draw Jumper's eye expressions and lay them out on a clip's timeline.

    python scissors_crab/tools/make_eyes.py --sheet sheet.png
    python scissors_crab/tools/make_eyes.py --stills scissors_crab/assets/eyes
    python scissors_crab/tools/make_eyes.py scissors_crab/motions/janken_lose.eyes.json \
        --duration 5.8 --out scissors_crab/renders/janken_lose/eyes

The style is the official face animation's (`tasks/jumper/dance/media/demo.mp4`):
flat cyan shapes on black, one 132 x 132 picture per round display. Every
expression is drawn for the display on the viewer's left (the robot's right eye) and
mirrored for the other, so a slanted brow or a tear stays symmetric about the face.

A timeline is JSON, `{"fps": 30, "keys": [[seconds, "expression"], ...]}`; each key
holds until the next. A `neutral` stretch blinks by itself every `BLINK_EVERY_S`.

Written for a timeline:

    <out>/R/0001.png ...   the robot's right eye, `--size` px, for Blender
    <out>/L/0001.png ...   the robot's left eye
    <out>/eyes_R.mp4, eyes_L.mp4   132 x 132, the displays' own resolution
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

#: The displays' resolution, px, as the official face animation has it.
NATIVE = 132
#: Supersampling for antialiased edges.
SS = 4
CYAN = (0, 255, 255)
TEAR = (90, 170, 255)
BLUSH = (255, 110, 170)
BLINK_EVERY_S = 2.8
BLINK_S = 0.12


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw, float]:
    s = NATIVE * SS
    img = Image.new("RGB", (s, s), (0, 0, 0))
    return img, ImageDraw.Draw(img), SS


def _box(cx, cy, w, h, k):
    return [(cx - w / 2) * k, (cy - h / 2) * k, (cx + w / 2) * k, (cy + h / 2) * k]


def _slanted(d, k, inner_drop: float, colour=CYAN) -> None:
    """A rounded block whose top edge slants: `inner_drop` > 0 lowers the inner
    corner (determined), < 0 raises it (sad). Inner is +x, toward the face's centre."""
    d.rounded_rectangle(_box(66, 72, 50, 40, k), radius=10 * k, fill=colour)
    # The cut line passes through the block's upper third, across the whole canvas.
    mid = 62
    outer, inner = mid - inner_drop / 2, mid + inner_drop / 2
    # Cut everything above the slanted line.
    d.polygon([(0, 0), (132 * k, 0), (132 * k, inner * k), (0, outer * k)], fill=(0, 0, 0))


def neutral(d, k):
    d.rounded_rectangle(_box(66, 66, 46, 56, k), radius=13 * k, fill=CYAN)


def blink(d, k):
    d.rounded_rectangle(_box(66, 70, 52, 7, k), radius=3.5 * k, fill=CYAN)


def serious(d, k):
    _slanted(d, k, inner_drop=26)


def sad(d, k):
    _slanted(d, k, inner_drop=-26)
    # A tear at the outer lower corner.
    x, y, r = 34, 100, 7
    d.ellipse([(x - r) * k, (y - r) * k, (x + r) * k, (y + r) * k], fill=TEAR)
    d.polygon([((x - r * 0.85) * k, (y - 3) * k), ((x + r * 0.85) * k, (y - 3) * k),
               (x * k, (y - 17) * k)], fill=TEAR)


def surprised(d, k):
    d.ellipse(_box(66, 64, 62, 62, k), fill=CYAN)


def happy(d, k):
    # ^ : an arch, thick, open at the bottom.
    d.arc(_box(66, 80, 66, 60, k), start=195, end=345, fill=CYAN, width=round(13 * k))


def shy(d, k):
    # > for this eye (pointing at the face's centre), and a blush below.
    w = round(10 * k)
    pts = [(46 * k, 44 * k), (82 * k, 64 * k), (46 * k, 84 * k)]
    d.line(pts, fill=CYAN, width=w, joint="curve")
    for p in (pts[0], pts[2]):
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=CYAN)
    d.ellipse(_box(40, 108, 40, 16, k), fill=BLUSH)


def sparkle(d, k):
    cx, cy, ro, ri = 66, 66, 38, 9
    pts = []
    for i in range(8):
        r = ro if i % 2 == 0 else ri
        a = math.pi / 2 + i * math.pi / 4
        pts.append(((cx + r * math.cos(a)) * k, (cy - r * math.sin(a)) * k))
    d.polygon(pts, fill=CYAN)


EXPRESSIONS = {f.__name__: f for f in (neutral, blink, serious, sad, surprised, happy, shy,
                                       sparkle)}


def draw(name: str, size: int, mirror: bool) -> Image.Image:
    img, d, k = _canvas()
    EXPRESSIONS[name](d, k)
    if mirror:
        img = ImageOps.mirror(img)
    return img.resize((size, size), Image.LANCZOS)


def sheet(path: Path) -> None:
    names = list(EXPRESSIONS)
    cell = 2 * NATIVE + 12
    out = Image.new("RGB", (cell * 4, cell * 2), (40, 40, 40))
    for i, name in enumerate(names):
        x, y = (i % 4) * cell + 4, (i // 4) * cell + 4
        out.paste(draw(name, NATIVE, mirror=False), (x, y))
        out.paste(draw(name, NATIVE, mirror=True), (x + NATIVE + 4, y))
    out.save(path)
    print(f"{len(names)} expressions -> {path}")


def stills(out: Path, size: int) -> None:
    """Every expression as `<name>_R.png` and `<name>_L.png`: the rig's default face."""
    out.mkdir(parents=True, exist_ok=True)
    for name in EXPRESSIONS:
        draw(name, size, mirror=False).save(out / f"{name}_R.png")
        draw(name, size, mirror=True).save(out / f"{name}_L.png")
    print(f"{len(EXPRESSIONS)} expressions x 2 eyes -> {out}")


def frames(keys: list[tuple[float, str]], duration: float, fps: int) -> list[str]:
    keys = sorted(keys)
    out = []
    for i in range(round(duration * fps) + 1):
        t = i / fps
        current = [k for k in keys if k[0] <= t]
        start, name = current[-1] if current else (0.0, "neutral")
        if name == "neutral" and (t - start) % BLINK_EVERY_S > BLINK_EVERY_S - BLINK_S:
            name = "blink"
        out.append(name)
    return out


def render(timeline: Path, duration: float, out: Path, size: int) -> None:
    spec = json.loads(timeline.read_text())
    fps = int(spec.get("fps", 30))
    unknown = {name for _, name in spec["keys"]} - set(EXPRESSIONS)
    if unknown:
        raise ValueError(f"{timeline}: unknown expressions {sorted(unknown)}; "
                         f"known: {sorted(EXPRESSIONS)}")
    seq = frames([tuple(k) for k in spec["keys"]], duration, fps)
    cache: dict[tuple[str, bool, int], Image.Image] = {}
    for side, mirror in (("R", False), ("L", True)):
        d = out / side
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.png"):
            old.unlink()
        for i, name in enumerate(seq, start=1):
            key = (name, mirror, size)
            if key not in cache:
                cache[key] = draw(name, size, mirror)
            cache[key].save(d / f"{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(fps), "-i",
             str(d / "%04d.png"), "-vf", f"scale={NATIVE}:{NATIVE}:flags=lanczos",
             "-pix_fmt", "yuv420p", "-c:v", "libx264", str(out / f"eyes_{side}.mp4")],
            check=True)
    print(f"{timeline.name}: {len(seq)} frames at {fps} fps -> {out}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("timeline", type=Path, nargs="?")
    ap.add_argument("--duration", type=float, help="seconds; the clip's length")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--size", type=int, default=256, help="px of the frames for Blender")
    ap.add_argument("--sheet", type=Path, help="write every expression side by side")
    ap.add_argument("--stills", type=Path, help="write every expression, both eyes, to this dir")
    args = ap.parse_args(argv)
    if args.sheet:
        sheet(args.sheet)
    if args.stills:
        stills(args.stills, args.size)
    if args.timeline:
        if args.duration is None or args.out is None:
            ap.error("a timeline needs --duration and --out")
        render(args.timeline, args.duration, args.out, args.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())

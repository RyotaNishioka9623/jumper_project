#!/usr/bin/env python3
"""Cut rendered takes into the video: clips, captions and sound effects, from one JSON.

    python scissors_crab/tools/edit.py scissors_crab/edit/scissors_crab.json \
        --out scissors_crab/renders/final/scissors_crab.mp4

The edit list:

    {
      "size": [1280, 720], "fps": 30,
      "font": "scissors_crab/external/fonts/mplus-rounded-1c/MPLUSRounded1c-ExtraBold.ttf",
      "clips": [{"file": "take.mp4", "in": 0.0, "out": 5.0}, ...],
      "captions": [{"text": "チョキしか出せないカニ", "sub": "This crab can only throw scissors",
                    "start": 0.3, "end": 3.0, "pos": "top", "size": 64,
                    "colour": [255, 255, 255]}, ...],
      "sounds": [{"file": "scissors_crab/external/se/パッ.mp3", "at": 1.2, "gain": 0.8,
                  "dur": 0.8}, ...],
      "fade_out": 1.5, "gain_db": 6.0
    }

Clips play one after another; caption and sound times are on that joined timeline,
in seconds. A sound's optional `dur` cuts it short, with a 0.1 s fade at the cut. Captions are drawn here (white, a dark rounded outline, an optional smaller
subtitle line) and overlaid while they are on; a short fade in and out softens them.
Re-timing captions or sounds needs no re-render of the takes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
FADE_S = 0.15


def caption_png(cap: dict, size: tuple[int, int], font_path: Path, out: Path) -> None:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fs = int(cap.get("size", 60))
    font = ImageFont.truetype(str(font_path), fs)
    sub_font = ImageFont.truetype(str(font_path), max(18, int(fs * 0.42)))
    colour = tuple(cap.get("colour", (255, 255, 255)))
    outline = tuple(cap.get("outline", (60, 40, 30)))
    lines = [(cap["text"], font, colour, max(4, fs // 9))]
    if cap.get("sub"):
        lines.append((cap["sub"], sub_font, (255, 255, 255), max(3, fs // 14)))
    heights = []
    for text, f, _, stroke in lines:
        box = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
        heights.append(box[3] - box[1])
    gap = int(fs * 0.18)
    total = sum(heights) + gap * (len(lines) - 1)
    pos = cap.get("pos", "bottom")
    margin = int(h * 0.07)
    y = {"top": margin, "center": (h - total) // 2, "bottom": h - margin - total}[pos]
    for (text, f, col, stroke), hh in zip(lines, heights):
        box = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
        x = (w - (box[2] - box[0])) // 2 - box[0]
        d.text((x, y - box[1]), text, font=f, fill=col, stroke_width=stroke, stroke_fill=outline)
        y += hh + gap
    img.save(out)


def build(spec: dict, out: Path) -> None:
    w, h = spec.get("size", (1280, 720))
    fps = spec.get("fps", 30)
    font = REPO / spec["font"]
    clips, captions, sounds = spec["clips"], spec.get("captions", []), spec.get("sounds", [])
    duration = sum(c["out"] - c["in"] for c in clips)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        args = ["ffmpeg", "-loglevel", "error", "-y"]
        for c in clips:
            args += ["-i", str(REPO / c["file"])]
        pngs = []
        for k, cap in enumerate(captions):
            png = tmp / f"cap{k}.png"
            caption_png(cap, (w, h), font, png)
            pngs.append(png)
            args += ["-loop", "1", "-t", f"{cap['end'] + FADE_S:.3f}", "-i", str(png)]
        for s in sounds:
            args += ["-i", str(REPO / s["file"])]
        # Silence the length of the video, so sound-free stretches still have audio.
        args += ["-f", "lavfi", "-t", f"{duration:.3f}", "-i",
                 "anullsrc=channel_layout=stereo:sample_rate=48000"]

        graph = []
        for i, c in enumerate(clips):
            graph.append(f"[{i}:v]trim=start={c['in']}:end={c['out']},setpts=PTS-STARTPTS,"
                         f"scale={w}:{h},fps={fps},format=yuv420p[v{i}]")
        graph.append("".join(f"[v{i}]" for i in range(len(clips)))
                     + f"concat=n={len(clips)}:v=1:a=0[base]")
        last = "base"
        for k, cap in enumerate(captions):
            idx = len(clips) + k
            st, en = cap["start"], cap["end"]
            graph.append(f"[{idx}:v]format=rgba,fade=t=in:st={st}:d={FADE_S}:alpha=1,"
                         f"fade=t=out:st={en - FADE_S}:d={FADE_S}:alpha=1[c{k}]")
            graph.append(f"[{last}][c{k}]overlay=0:0:enable='between(t,{st},{en})'[o{k}]")
            last = f"o{k}"
        fade = spec.get("fade_out")
        if fade:
            graph.append(f"[{last}]fade=t=out:st={duration - fade:.3f}:d={fade}[vout]")
        else:
            graph.append(f"[{last}]null[vout]")

        first_sound = len(clips) + len(captions)
        silence = first_sound + len(sounds)
        mix = [f"[{silence}:a]"]
        for j, s in enumerate(sounds):
            ms = round(s["at"] * 1000)
            cut = ""
            if s.get("dur"):
                d = float(s["dur"])
                cut = f"atrim=end={d},afade=t=out:st={max(d - 0.1, 0.0):.3f}:d=0.1,"
            graph.append(f"[{first_sound + j}:a]{cut}aresample=48000,"
                         f"aformat=channel_layouts=stereo,"
                         f"volume={s.get('gain', 1.0)},adelay={ms}|{ms}[a{j}]")
            mix.append(f"[a{j}]")
        graph.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first[mixed0]")
        # The whole mix up by `gain_db`, a limiter catching where effects overlap.
        graph.append(f"[mixed0]volume={spec.get('gain_db', 0.0)}dB,"
                     f"alimiter=limit=0.97:level=0[mixed]")
        if fade:
            graph.append(f"[mixed]afade=t=out:st={duration - fade:.3f}:d={fade}[aout]")
        else:
            graph.append("[mixed]anull[aout]")

        args += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
                 "-t", f"{duration:.3f}", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(args, check=True)
    print(f"{len(clips)} clips, {len(captions)} captions, {len(sounds)} sounds, "
          f"{duration:.1f} s -> {out}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    build(json.loads(args.spec.read_text()), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

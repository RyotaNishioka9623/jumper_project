#!/usr/bin/env python3
"""Cut the camera version's recording into a post: a title card, then two games.

    python scissors_crab/edit/make_live_demo.py
    python scissors_crab/tools/edit.py scissors_crab/edit/live_demo.json \
        --out scissors_crab/renders/live/live_demo.mp4

The recording is `interactive/janken_cam.py --record`'s, converted to H.264
(`renders/live/demo_x.mp4`, 1280x720, 29.1 s, 2026-10-28): a draw then the crab's
win, a draw then its loss. The waits before and between the games are cut, at the
points where "press space" leaves and comes back.

The card is the first thing X shows of the video (a free account cannot choose a
thumbnail), so it says what this is, from its first frame: the crab's half of a
still of the banzai, enlarged and dimmed, under the title.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

REPO = Path(__file__).resolve().parents[2]
LIVE = "scissors_crab/renders/live/"
SOURCE = LIVE + "demo_x.mp4"
CARD = LIVE + "card.mp4"
CARD_S = 2.2
#: (in, out) in the recording, seconds: from just before space is pressed to just
#: before "press space" shows again.
GAMES = ((5.0, 15.3), (16.67, 28.3))
#: The card's still: the banzai after "paper vs scissors".
STILL_AT = 10.4


def make_card() -> None:
    still = REPO / LIVE / "card.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(STILL_AT), "-i",
                    str(REPO / SOURCE), "-frames:v", "1", str(still)], check=True)
    # The crab's half of the window (janken_cam.compose: x 640-1280, y 120-600),
    # enlarged to fill the frame; the app's own captions are left out.
    img = Image.open(still).convert("RGB").crop((640, 120, 1280, 600)).resize((1280, 960))
    img = img.crop((0, 140, 1280, 860)).filter(ImageFilter.GaussianBlur(2))
    ImageEnhance.Brightness(img).enhance(0.6).save(still)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", str(still),
                    "-t", str(CARD_S), "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(REPO / CARD)], check=True)


def main() -> None:
    make_card()
    games = sum(b - a for a, b in GAMES)
    spec = {
        "size": [1280, 720],
        "fps": 30,
        "font": "scissors_crab/external/fonts/mplus-rounded-1c/MPLUSRounded1c-ExtraBold.ttf",
        "clips": [{"file": CARD, "in": 0.0, "out": CARD_S}]
                 + [{"file": SOURCE, "in": a, "out": b} for a, b in GAMES],
        "captions": [
            {"text": "カメラでカニとじゃんけん", "sub": "Rock-paper-scissors with the crab, live",
             "start": 0.0, "end": CARD_S, "pos": "center", "size": 84, "fade_in": False},
        ],
        "sounds": [],
        "fade_out": 0.8,
    }
    out = Path(__file__).resolve().parent / "live_demo.json"
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print(f"{out}: {CARD_S + games:.1f} s")


if __name__ == "__main__":
    main()

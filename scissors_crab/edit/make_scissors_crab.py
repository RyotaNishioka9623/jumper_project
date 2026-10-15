#!/usr/bin/env python3
"""Write the edit list for the video, `scissors_crab.json`, from render frame numbers.

    python scissors_crab/edit/make_scissors_crab.py
    python scissors_crab/tools/edit.py scissors_crab/edit/scissors_crab.json \
        --out scissors_crab/renders/final/scissors_crab.mp4

Four takes, rendered at 1920x1080 into `scissors_crab/renders/final/` (README.md has
the commands):

- `lose_ots.mp4`, render frames 1-230: the losing game over the human's shoulder,
- `lose_close.mp4`, frames 200-338: the same take, the crab's face close up,
- `win_ending.mp4`, frames 70-480: the winning game (janken_win_jump), then
  `ending.py`'s camera across the room to the two crabs drawing forever,
- `win_ending_tail.mp4`, frames 481-540: the same shot two seconds longer
  (`ending.py --length 540`), for the title to be read.

**The premise is not told; the viewer works it out.** The video opens on the game
itself -- the fist coming up, "jan, ken" -- not on a title. Scissors against rock,
scissors again against paper, then two crabs throwing scissors at each other
forever: by then the viewer has thought "wait, can it only throw scissors?", and the
title arrives last, over the endless draw, as the answer. So the only other caption
is "one more time!", which marks the cut from the close-up back to the game as a
second round. Every caption is Japanese with an English line under it.

Every caption and sound is placed at a render frame of the take it belongs to --
the beats are the choreography's (`motions/janken_common.py`, `make_janken_*.py`,
the eye timelines) plus the converter's 12-frame lead-in -- so a cut point can move
without re-timing anything by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPS = 30
SE = "scissors_crab/external/se/"
FINAL = "scissors_crab/renders/final/"

#: (file, first render frame in the file, cut in, cut out) -- in inclusive, out not.
TAKES = (
    # From the fist coming into frame, 0.4 s before "jan" (96): the first frame is
    # what X shows before the video plays. The practice snips before it are cut.
    ("lose_ots", 1, 84, 211),       # up to the head going down
    ("lose_close", 200, 211, 296),  # the crying, up to the lead-out back to HOME
    ("win_ending", 70, 80, 481),    # from the fist raised for the rematch
    ("win_ending_tail", 481, 481, 541),
)


def timeline():
    """Output time of render frame `f` in take `name`, and the total length."""
    starts, t = {}, 0.0
    for name, _, cin, cout in TAKES:
        starts[name] = t - cin / FPS
        t += (cout - cin) / FPS
    return lambda name, f: round(starts[name] + f / FPS, 3), round(t, 3)


def main() -> None:
    at, duration = timeline()

    def L(f):
        return at("lose_ots", f)

    def C(f):
        return at("lose_close", f)

    def W(f):  # the tail continues the shot, so its frames are on the same line
        return at("win_ending", f)

    def cap(text, sub, start, end, pos="top", size=92):
        return {"text": text, "sub": sub, "start": start, "end": end, "pos": pos,
                "size": size}

    def snd(name, t, gain=0.8, dur=None):
        s = {"file": SE + name + ".mp3", "at": t, "gain": gain}
        if dur:
            s["dur"] = dur
        return s

    captions = [
        # The rematch: from the fist raised (88) to just before pon (120).
        cap("もう一回！", "One more time!", W(81), W(116)),
        # The answer, over the pair drawing: their "sho" falls on 306 + 36k, so two
        # and a half rounds play before it, and it holds to the end.
        cap("チョキしか出せないカニ", "The crab that can only throw scissors", W(386),
            duration, size=110),
        cap("Jumper オープンソースで強化学習",
            "Trained in simulation with the Jumper open-source toolkit"
            " · scene: KingKong Robotics jumper-design",
            W(400), duration, pos="bottom", size=58),
    ]
    # Lose: jan 96, ken 108, pon 120, flinch 128, head down from 199; crying from
    # 221 (eyes), sobs to 294. Win: pon 120, hops at 140 and 155 (the replay's
    # take-offs), sparkle 161, snip 168, remembers 176, hides 186, peeks 210; the
    # camera leaves at 230 and reaches the pair at 305.
    sounds = [
        snd("パッ", L(95), 0.6, dur=0.4),
        snd("パッ", L(107), 0.6, dur=0.4),
        snd("ジャン！", L(119), 0.8, dur=1.2),
        snd("ショック2", L(127), 0.7, dur=1.8),
        snd("しょげる", L(198), 0.8),
        snd("涙のしずく", C(221), 0.8),
        snd("チーン1", C(284), 0.7, dur=1.2),
        snd("パッ", W(95), 0.6, dur=0.4),
        snd("パッ", W(107), 0.6, dur=0.4),
        snd("ジャン！", W(119), 0.8, dur=1.0),
        snd("ジャンプ", W(139), 0.8),
        snd("ジャンプ", W(154), 0.8),
        snd("可愛く輝く1", W(161), 0.6),
        snd("ハサミでチョキチョキ", W(166), 0.5, dur=0.6),
        snd("驚く", W(175), 0.7),
        snd("心臓の鼓動2", W(186), 0.8),
        snd("目をパチパチ", W(209), 0.6),
        snd("シーン切り替え2", W(231), 0.4),
        snd("パッ", W(306), 0.35, dur=0.3),
        snd("パッ", W(342), 0.35, dur=0.3),
        snd("パッ", W(378), 0.35, dur=0.3),
        snd("キラッ1", W(386), 0.6),
        snd("ちゃんちゃん♪1", round(duration - 1.75, 3), 0.9),
    ]
    spec = {
        "size": [1920, 1080],
        "fps": FPS,
        "font": "scissors_crab/external/fonts/mplus-rounded-1c/MPLUSRounded1c-ExtraBold.ttf",
        "clips": [{"file": FINAL + name + ".mp4", "in": round((cin - first) / FPS, 3),
                   "out": round((cout - first) / FPS, 3)} for name, first, cin, cout in TAKES],
        "captions": captions,
        "sounds": sounds,
        "fade_out": 1.6,
        # Effects only, mixed at their own levels, peak at -7 dB: up 6 dB.
        "gain_db": 6.0,
    }
    out = HERE / "scissors_crab.json"
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print(f"{out}: {duration:.2f} s, {len(captions)} captions, {len(sounds)} sounds")


if __name__ == "__main__":
    main()

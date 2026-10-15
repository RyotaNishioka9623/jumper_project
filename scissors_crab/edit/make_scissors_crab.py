#!/usr/bin/env python3
"""Write the edit list for the video, `scissors_crab.json`, from render frame numbers.

    python scissors_crab/edit/make_scissors_crab.py
    python scissors_crab/tools/edit.py scissors_crab/edit/scissors_crab.json \
        --out scissors_crab/renders/final/scissors_crab.mp4

Three takes, rendered at 1920x1080 into `scissors_crab/renders/final/` (README.md has
the commands):

- `lose_ots.mp4`, render frames 1-230: the losing game over the human's shoulder,
- `lose_close.mp4`, frames 200-338: the same take, the crab's face close up,
- `win_ending.mp4`, frames 70-480: the winning game (janken_win_jump), then
  `ending.py`'s camera across the room to the two crabs drawing forever.

Every caption and sound is placed at a render frame of the take it belongs to --
the beats are the choreography's (`motions/janken_common.py`, `make_janken_*.py`,
the eye timelines) plus the converter's 12-frame lead-in -- so a cut point can move
without re-timing anything by hand. Captions are Japanese with an English line under
them.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPS = 30
SE = "scissors_crab/external/se/"
FINAL = "scissors_crab/renders/final/"

#: (file, first render frame in the file, cut in, cut out) -- frames, inclusive in.
TAKES = (
    ("lose_ots", 1, 1, 211),      # up to the head going down
    ("lose_close", 200, 211, 296),  # the crying, up to the lead-out back to HOME
    ("win_ending", 70, 80, 480),  # from the fist raised for the rematch
)


def timeline():
    """Output time of render frame `f` in take `name`."""
    starts, t = {}, 0.0
    for name, _, cin, cout in TAKES:
        starts[name] = t - cin / FPS
        t += (cout - cin) / FPS
    return lambda name, f: round(starts[name] + f / FPS, 3), round(t, 3)


def main() -> None:
    at, duration = timeline()
    L = lambda f: at("lose_ots", f)
    C = lambda f: at("lose_close", f)
    W = lambda f: at("win_ending", f)

    def cap(text, sub, start, end, pos="top", size=64):
        return {"text": text, "sub": sub, "start": start, "end": end, "pos": pos,
                "size": size}

    def snd(name, t, gain=0.8, dur=None):
        s = {"file": SE + name + ".mp3", "at": t, "gain": gain}
        if dur:
            s["dur"] = dur
        return s

    # The shared opening, in render frames: sparkle eyes 30, snips 47-74,
    # jan 96, ken 108, pon 120 (stage.py's READY..PON).
    captions = [
        cap("チョキしか出せないカニ", "The crab that can only throw scissors", 0.2, L(88),
            size=76),
        cap("じゃん", "Rock,", L(94), L(106)),
        cap("けん", "paper,", L(106), L(118)),
        cap("ぽん！", "scissors!", L(118), L(136)),
        # Lose: flinch 128, blank stare, head down from 199.
        cap("グーには勝てない…", "Scissors lose to rock...", L(142), L(204)),
        # Close up: claws down, crying from 221 (eyes), sobs to 294.
        cap("チョキしか出せないから…", "...because it can only throw scissors", C(224),
            C(292), pos="bottom"),
        # Win: rematch from the fist raised (88), pon 120, claw up 128, hops at 140
        # and 155 (the replay's take-offs), snip 168, remembers 176, hides 186, peeks
        # 210, hides 222; the camera leaves at 230 and reaches the pair at 305.
        cap("もう一回！", "One more time!", W(81), W(116)),
        cap("勝った！", "I won!", W(127), W(165)),
        cap("…はっ", "...oh", W(176), W(196)),
        cap("はずかしい…", "so embarrassing...", W(197), W(238)),
        cap("いっぽう、カニどうしだと…", "Meanwhile, crab vs. crab...", W(262), W(304)),
        # The pair's "aiko de sho": each cycle 36 frames, "sho" on scissors at 306+36k.
        cap("あいこでしょ！", "Draw! Again!", W(318), W(344)),
        cap("あいこでしょ！", "Draw! Again!", W(354), W(380)),
        cap("あいこでしょ！", "Draw! Again!", W(390), W(416)),
        cap("（おわらない）", "(forever)", W(424), W(480)),
        cap("Jumper オープンソースで強化学習",
            "Trained in simulation with the Jumper open-source toolkit"
            " · scene: KingKong Robotics jumper-design",
            W(396), W(480), pos="bottom", size=34),
    ]
    sounds = [
        snd("キラッ1", L(29), 0.6),
        snd("ハサミでチョキチョキ", L(45), 0.6, dur=1.1),
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
    }
    out = HERE / "scissors_crab.json"
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")
    print(f"{out}: {duration:.2f} s, {len(captions)} captions, {len(sounds)} sounds")


if __name__ == "__main__":
    main()

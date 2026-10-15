#!/usr/bin/env python3
"""Count each post in a Markdown file the way X does, against the 280 limit.

    python scissors_crab/tools/x_length.py scissors_crab/post/x_posts.md

Every fenced ```text block is one post. The weighting is twitter-text v3's: a code
point in the light ranges (Latin and the like) counts 1, anything else -- CJK, emoji
-- counts 2, and every URL counts 23 whatever its length. On a free account a post
must come to 280 or less, which is 140 Japanese characters.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIMIT = 280
URL_LENGTH = 23
LIGHT = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
URL = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?", re.IGNORECASE)
BLOCK = re.compile(r"^```text\n(.*?)\n```", re.DOTALL | re.MULTILINE)


def weighted(text: str) -> int:
    n = URL_LENGTH * len(URL.findall(text))
    for ch in URL.sub("", text):
        cp = ord(ch)
        if 0xFE00 <= cp <= 0xFE0F or cp == 0x200D:  # variation selectors, joiners
            continue
        n += 1 if any(a <= cp <= b for a, b in LIGHT) else 2
    return n


def main(argv: list[str] | None = None) -> int:
    path = Path((argv or sys.argv[1:])[0])
    posts = BLOCK.findall(path.read_text(encoding="utf-8"))
    over = 0
    for k, post in enumerate(posts, 1):
        n = weighted(post)
        over += n > LIMIT
        first = post.splitlines()[0][:40]
        print(f"{k}. {n:3d} / {LIMIT}{'  OVER' if n > LIMIT else ''}  {first}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())

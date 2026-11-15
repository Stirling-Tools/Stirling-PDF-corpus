#!/usr/bin/env python3
"""Writes byte-level mutations of the synthetic samples, for crash and recovery testing.

    python3 make_damaged.py SYNTHETIC_DIR OUT_DIR [COUNT_PER_FILE]

Each sample's mutants are seeded by its path, so they stay the same when other
samples are added or changed. damaged-recovery/ keeps a few of them, chosen
because one engine opens them and the other does not.
"""

import os
import random
import sys

TOKENS = [
    b"0", b"-1", b"99999999", b"null", b"[]", b"<<>>", b"/Type", b"R", b"obj", b"endobj",
    b"stream", b"1e308", b"-0.0", b"(", b")", b"<", b">", b"/FlateDecode", b"BT", b"ET",
    b"Tj", b"q", b"Q", b"cm", b"Do",
]


def mutate(rng, data):
    b = bytearray(data)
    for _ in range(rng.randint(1, 6)):
        op = rng.random()
        i = rng.randrange(len(b))
        if op < 0.35:
            b[i] = rng.randrange(256)
        elif op < 0.6:
            del b[i : min(len(b), i + rng.randint(1, 40))]
        elif op < 0.85:
            b[i:i] = rng.choice(TOKENS)
        else:
            j = min(len(b), i + rng.randint(1, 200))
            k = rng.randrange(len(b))
            b[k:k] = b[i:j]
    return bytes(b)


def main(src, out, per_file=5):
    seeds = sorted(
        os.path.join(d, f)
        for d, _, fs in os.walk(src)
        for f in fs
        if f.endswith(".pdf") and "encrypted" not in f
    )
    os.makedirs(out, exist_ok=True)
    for s in seeds:
        data = open(s, "rb").read()
        rng = random.Random("20261115:" + os.path.relpath(s, src).replace(os.sep, "/"))
        for k in range(per_file):
            path = os.path.join(out, f"{os.path.basename(s)[:-4]}-m{k}.pdf")
            with open(path, "wb") as f:
                f.write(mutate(rng, data))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)

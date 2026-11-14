#!/usr/bin/env python3
"""Writes a TSV manifest row for every PDF under the given folders.

    python3 build_manifest.py NOTES.tsv OUT.tsv FOLDER... [--pdfium PDFIUM.tsv]

NOTES.tsv has columns pattern, licence, source, tags, description; the first
pattern (fnmatch against the path relative to this script's parent folder) that
matches a file supplies those columns, and "{name}" in a description is replaced
by the file's stem. Size, hash, page count, fonts and qpdf's verdict are measured,
using pdfinfo, pdffonts and qpdf when they are on PATH. PDFIUM.tsv is the output
of pdfium_open.mjs run over the same root.
"""

import csv
import fnmatch
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLUMNS = [
    "path", "bytes", "sha256", "pages", "fonts_not_embedded", "fonts_embedded",
    "qpdf_check", "pdfium", "licence", "source", "tags", "description",
]


def run(args):
    try:
        done = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return done.returncode, done.stdout


def pages(path):
    if not shutil.which("pdfinfo"):
        return ""
    _, out = run(["pdfinfo", path])
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return line.split()[-1]
    return ""


def fonts(path):
    if not shutil.which("pdffonts"):
        return "", ""
    _, out = run(["pdffonts", path])
    embedded, missing = set(), set()
    for line in out.splitlines()[2:]:
        parts = line.split()
        if len(parts) < 7 or parts[-5] not in ("yes", "no"):
            continue
        name = parts[0].split("+", 1)[-1]
        (embedded if parts[-5] == "yes" else missing).add(name)
    return " ".join(sorted(missing)), " ".join(sorted(embedded))


def qpdf_check(path):
    if not shutil.which("qpdf"):
        return ""
    code, _ = run(["qpdf", "--check", path])
    return {0: "ok", 3: "warnings", 2: "errors"}.get(code, f"exit {code}")


def load_notes(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f, delimiter="\t")]


def load_pdfium(path):
    results = {}
    if path:
        with open(path, encoding="utf-8") as f:
            for line in f:
                rel, _, rest = line.rstrip("\n").partition("\t")
                results[rel] = rest.replace("\t", " ")
    return results


def main(argv):
    pdfium_path = None
    if "--pdfium" in argv:
        i = argv.index("--pdfium")
        pdfium_path = argv[i + 1]
        argv = argv[:i] + argv[i + 2 :]
    if len(argv) < 3:
        sys.exit(__doc__)
    notes, out_path, folders = load_notes(argv[0]), argv[1], argv[2:]
    pdfium = load_pdfium(pdfium_path)
    rows = []
    for folder in folders:
        for dirpath, _, files in os.walk(folder):
            for name in sorted(files):
                if not name.lower().endswith(".pdf"):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, ROOT)
                note = next((n for n in notes if fnmatch.fnmatch(rel, n["pattern"])), None)
                if note is None:
                    sys.exit(f"no note matches {rel}")
                with open(full, "rb") as f:
                    data = f.read()
                missing, embedded = fonts(full)
                stem = os.path.splitext(name)[0]
                rows.append({
                    "path": rel,
                    "bytes": str(len(data)),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "pages": pages(full),
                    "fonts_not_embedded": missing,
                    "fonts_embedded": embedded,
                    "qpdf_check": qpdf_check(full),
                    "pdfium": pdfium.get(rel, ""),
                    "licence": note["licence"],
                    "source": note["source"].replace("{name}", stem),
                    "tags": note["tags"],
                    "description": note["description"].replace("{name}", stem),
                })
    rows.sort(key=lambda r: r["path"])
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1:])

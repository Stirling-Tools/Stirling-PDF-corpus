#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: compare_optimizer_runs.sh BASE_CLI NEW_CLI PDF_DIR OUT_DIR [extra office-convert options...]" >&2
  echo "  BASE_CLI, NEW_CLI  office-convert launchers (cli/build/install/cli/bin/cli of two builds)" >&2
  echo "  PDF_DIR            folder of PDFs; subfolders are flattened into OUT_DIR/in" >&2
  echo "  needs pdftoppm (poppler) for the render comparison" >&2
  exit 2
}

[ $# -ge 4 ] || usage
base_cli=$1
new_cli=$2
pdfs=$3
out=$4
shift 4

rm -rf "$out"
mkdir -p "$out/in" "$out/base" "$out/new" "$out/render"
find "$pdfs" -type f -name '*.pdf' -exec cp {} "$out/in/" \;

"$base_cli" "$out/in" --optimize -o "$out/base" --timeout 120 "$@" > "$out/base.log" 2>&1 || true
"$new_cli" "$out/in" --optimize -o "$out/new" --timeout 120 "$@" > "$out/new.log" 2>&1 || true

echo "base: $(grep -c '^OK' "$out/base.log" || true) ok, $(grep -c '^FAIL' "$out/base.log" || true) failed"
echo "new:  $(grep -c '^OK' "$out/new.log" || true) ok, $(grep -c '^FAIL' "$out/new.log" || true) failed"

diff <(grep '^FAIL' "$out/base.log" | sed 's/:.*//' | sort) \
     <(grep '^FAIL' "$out/new.log" | sed 's/:.*//' | sort) > "$out/failures.diff" \
  && echo "same failures" || { echo "failures changed:"; cat "$out/failures.diff"; }

same=0
for f in "$out"/base/*.pdf; do
  name=$(basename "$f")
  other="$out/new/$name"
  if [ ! -f "$other" ]; then
    echo "missing in new: $name"
    continue
  fi
  if cmp -s "$f" "$other"; then
    same=$((same + 1))
    continue
  fi
  rm -f "$out"/render/*
  pdftoppm -r 40 -l 20 "$f" "$out/render/a" 2>/dev/null || true
  pdftoppm -r 40 -l 20 "$other" "$out/render/b" 2>/dev/null || true
  a=$(cat "$out"/render/a* 2>/dev/null | shasum | cut -c1-12)
  b=$(cat "$out"/render/b* 2>/dev/null | shasum | cut -c1-12)
  verdict=$([ "$a" = "$b" ] && echo "renders the same" || echo "RENDERS DIFFERENTLY")
  echo "$name: $(stat -f%z "$f" 2>/dev/null || stat -c%s "$f") -> $(stat -f%z "$other" 2>/dev/null || stat -c%s "$other") bytes, $verdict"
done
echo "$same files byte-identical"

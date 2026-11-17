#!/bin/sh
# Rebuilds producers/ from the shared content: Chrome (HTML), pdfLaTeX, ReportLab and PyMuPDF.
# Needs Chrome, pdflatex with tikz/pgfplots/listings, Python with reportlab and pymupdf, Liberation fonts.
set -eu
cd "$(dirname "$0")"
out=../../producers
work=$(mktemp -d)
python html_gen.py "$work/html"
python tex_gen.py "$work/tex"
python py_gen.py "$work/py"
python watermark_gen.py "$out/reportlab-watermark.pdf"
"${CHROME:-google-chrome}" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$out/chrome-code.pdf" "file://$work/html/code.html"
(cd "$work/tex" && for n in report code twocol; do pdflatex -interaction=nonstopmode $n.tex >/dev/null; pdflatex -interaction=nonstopmode $n.tex >/dev/null; cp $n.pdf "$OLDPWD/$out/pdflatex-$n.pdf"; done)
cp "$work/py/mupdf-rotated.pdf" "$out/"
rm -rf "$work"

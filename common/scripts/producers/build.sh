#!/bin/sh
# Rebuilds producers/ from the shared content: Chrome (HTML), pdfLaTeX, ReportLab and PyMuPDF.
# Needs Chrome, LibreOffice, pdflatex with tikz/pgfplots/listings/lmodern, Python with reportlab, pymupdf, python-docx and openpyxl, Liberation fonts.
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
python structure_gen.py "$work/structure"
cp "$work/structure/"reportlab-labels.pdf "$work/structure/"reportlab-qrslip.pdf "$work/structure/"reportlab-sparse.pdf "$work/structure/"mupdf-slides.pdf "$out/"
"${SOFFICE:-soffice}" --headless --convert-to pdf --outdir "$work/structure" "$work/structure/finance.xlsx" "$work/structure/cells.docx" >/dev/null
cp "$work/structure/finance.pdf" "$out/libreoffice-finance.pdf"; cp "$work/structure/cells.pdf" "$out/libreoffice-cells.pdf"
(cd "$work/structure/tex" && pdflatex -interaction=nonstopmode levels.tex >/dev/null && pdflatex -interaction=nonstopmode levels.tex >/dev/null && cp levels.pdf "$OLDPWD/$out/pdflatex-levels.pdf")
rm -rf "$work"

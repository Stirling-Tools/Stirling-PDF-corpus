#!/bin/sh
# Builds latex-math/ from math.tex: Computer Modern, Latin Modern and Times maths with pdfLaTeX, and XeLaTeX.
set -e
cd "$(dirname "$0")"
out=../../latex-math
pdflatex -interaction=nonstopmode -jobname=cm-pdflatex math.tex
sed 's/\usepackage{amsmath,amssymb}/&\n\usepackage{lmodern}/' math.tex > lmodern.tex
pdflatex -interaction=nonstopmode -jobname=lmodern-pdflatex lmodern.tex
sed 's/\usepackage{amsmath,amssymb}/&\n\usepackage{mathptmx}/' math.tex > mathptmx.tex
pdflatex -interaction=nonstopmode -jobname=times-mathptmx-pdflatex mathptmx.tex
xelatex -interaction=nonstopmode -jobname=cm-xelatex math.tex
mv cm-pdflatex.pdf lmodern-pdflatex.pdf times-mathptmx-pdflatex.pdf cm-xelatex.pdf "$out"/
rm -f lmodern.tex mathptmx.tex *.aux *.log

set -e
B=/tmp/b; rm -rf $B; mkdir -p $B; cd $B
cp /src/*.tex .
export SOURCE_DATE_EPOCH=1100000000 FORCE_SOURCE_DATE=1
M=$(kpsewhich pdftex.map)
sed -E 's/ <<?[^ ]*\.(pfb|pfa|ttf|otf)//g; s/ <\[?[^ ]*\.pfb//g' $M > noembed.map
: > empty.map
DOCS="article-math beamer-slide table-report biblio accents ligatures twocol"
pdf() { v=$1; fonts=$2; map=$3; mkdir -p /out/$v
  for d in $DOCS; do
    pre="\\def\\FONTS{$fonts}"; [ -n "$map" ] && pre="$pre\\pdfmapfile{$map}"; [ "$4" = notu ] && pre="$pre\\AtBeginDocument{\\pdfgentounicode=0}"
    pdflatex -interaction=batchmode -jobname=$d "$pre\\input{$d}" >/dev/null 2>&1 || true
    pdflatex -interaction=batchmode -jobname=$d "$pre\\input{$d}" >/dev/null 2>&1 || echo "FAIL $v $d"
    cp $d.pdf /out/$v/$d.pdf || true; rm -f $d.pdf $d.aux $d.log $d.nav $d.out $d.snm $d.toc
  done; }
pdf a-embed-ot1 ot1 ""
pdf b-noembed-ot1 ot1 noembed.map notu
pdf c-embed-t1 t1 ""
pdf c-noembed-t1 t1 noembed.map notu
pdf c-embed-lm lm ""
pdf c-noembed-lm lm noembed.map notu
pdf g-embed-ptm ptm ""
pdf g-noembed-ptm ptm noembed.map notu
mkdir -p /out/d-pk-type3 /out/_e-dvipdfmx-embed
for d in $DOCS; do
  latex -interaction=batchmode -jobname=$d "\\def\\FONTS{ot1}\\input{$d}" >/dev/null 2>&1 || true
  latex -interaction=batchmode -jobname=$d "\\def\\FONTS{ot1}\\input{$d}" >/dev/null 2>&1 || echo "FAIL dvi $d"
  dvips -q -u empty.map -D 600 -o $d.ps $d.dvi >/dev/null 2>&1 || echo "FAIL dvips $d"
  ps2pdf -dPDFSETTINGS=/default $d.ps /out/d-pk-type3/$d.pdf || echo "FAIL ps2pdf $d"
  dvipdfmx -q -o /out/_e-dvipdfmx-embed/$d.pdf $d.dvi >/dev/null 2>&1 || echo "FAIL dvipdfmx $d"
  rm -f $d.dvi $d.ps $d.aux $d.log $d.nav $d.out $d.snm $d.toc
done
mkdir -p /out/f-lualatex-embed /out/f-xelatex-embed
for d in $DOCS; do
  sed 's/\\input{fonts}/\\usepackage{fontspec}\\setmainfont{TeX Gyre Termes}/' $d.tex > x-$d.tex
  lualatex -interaction=batchmode -jobname=$d x-$d.tex >/dev/null 2>&1 || true
  lualatex -interaction=batchmode -jobname=$d x-$d.tex >/dev/null 2>&1 || echo "FAIL lua $d"
  cp $d.pdf /out/f-lualatex-embed/ 2>/dev/null; rm -f $d.pdf $d.aux $d.log $d.nav $d.out $d.snm $d.toc
  xelatex -interaction=batchmode -jobname=$d x-$d.tex >/dev/null 2>&1 || true
  xelatex -interaction=batchmode -jobname=$d x-$d.tex >/dev/null 2>&1 || echo "FAIL xe $d"
  cp $d.pdf /out/f-xelatex-embed/ 2>/dev/null; rm -f $d.pdf $d.aux $d.log $d.nav $d.out $d.snm $d.toc
done
chmod -R a+rwX /out

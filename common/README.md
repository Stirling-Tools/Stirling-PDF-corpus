# Common regression PDFs

A shared pool of small PDFs that break things: missing fonts, odd encodings, damaged
structure, awkward layouts. Each one should be small enough to sit in a unit or
end-to-end test and specific enough that a failure points at one cause.

## Rules for adding files

- **Licence first.** Only add a file if we made it, or its licence lets anyone
  redistribute it. Check the fonts embedded in it as well: `pdffonts file.pdf`. Don't
  add files that embed Microsoft, Apple or other commercial fonts. The fonts in this
  folder are OFL, GUST, URW (GPL with font exception), Liberation, DejaVu, Noto,
  Carlito, AMS, TeX bitmaps, LibreOffice's OpenSymbol (MPL 2.0) or Tesseract's
  GlyphLessFont (Apache 2.0). Downloaded documents, customer files and bug-report
  attachments stay out. Instead, build a minimal reproduction, and add the
  generator script if you can.
- **Small.** Nearly half the files here are under 7 KB, and none is over 310 KB. Leave out
  images and embedded media unless they are the point of the file. Keep each file well
  under the 20 MB limit.
- **No personal data.** Check `pdfinfo` and the XMP metadata for names, email
  addresses and local paths before committing.
- **Describe every file.** Add rows to a `notes/<contribution>.tsv` file, then run
  `scripts/build_manifest.py` to write `manifest-<contribution>.tsv`. Keeping the
  manifests separate lets contributions merge without conflicts. Combine them later
  with `cat manifest-*.tsv`, keeping a single header line.
- **Unique paths.** Put each set in its own folder.

## Manifest columns

`path`, `bytes`, `sha256`, `pages`, `fonts_not_embedded`, `fonts_embedded`,
`qpdf_check` (ok, warnings or errors from `qpdf --check`), `pdfium` (page and
character counts from `scripts/pdfium_open.mjs`, or the PDFium error code),
`licence`, `source`, `tags`, `description`.

## Sets in this folder

| Folder | Files | What it is for |
| --- | --- | --- |
| `synthetic/` | 97 | One hand-built PDF per problem, from `scripts/make_synthetic.py`, grouped into `fonts`, `text`, `layout`, `pages`, `content`, `structure`, `annotations`, `interactive` (forms, JavaScript, links and named destinations, deep bookmarks, annotations with appearances, a junk signature, attachments), `metadata` (odd Info values, broken and disagreeing XMP), `graphics` (transparency, spot colours, shadings and patterns), `edge` (page-tree and outline cycles, a lying `/Count`, odd `/Rotate` and MediaBox values, actions, attachments, NeedAppearances forms, incremental chains) and `regressions` (a reproduction of an oblique-font redaction bug, plus two controls for bugs that need other files to reproduce). |
| `fonts-missing-latex/` | 98 | The same seven LaTeX documents built 14 ways: fonts embedded, not embedded, embedded but with the font program stripped, or as Type 3 bitmaps. Each `*-embed-*` folder is the control for its `*-noembed-*` or `*-stripped` partner. |
| `latex-documents/` | 3 | Two-column reading order, hyphenation and maths, from the Office Convert benchmark. |
| `latex-math/` | 4 | One page of inline and display maths built four ways: Computer Modern, Latin Modern and Times (mathptmx) with pdfLaTeX, and XeLaTeX. From `scripts/latex-math/build.sh`. |
| `multilingual-udhr/` | 49 | One PDF per script or language (Arabic, Hebrew, the Indic scripts, CJK, Thai, Ethiopic, Tibetan, Mongolian, emoji and others), mostly Universal Declaration of Human Rights text. |
| `stirling-fixtures/` | 11 | Small generated fixtures copied from Stirling-PDF's editor tests: forms, annotations, links, tables, tagging, split content streams. |
| `damaged-recovery/` | 8 | Byte-mutated copies of synthetic samples that one engine opens and the other refuses: five PDFBox repairs but PDFium rejects, three the other way round. From `scripts/make_damaged.py`. |
| `optimizer/` | 18 | Filters, colour spaces, images, JPEG 2000 and structure that broke optimisation or greyscale conversion. Its own `optimizer/README.md` describes each file, and `scripts/make_optimizer_cases.py` rebuilds them. |
| `conformance/pdfa/` | 20 | Passing PDF/A-1b (tagged and untagged), 2b, 2u, 3b and 4 controls, a valid 3b with an XML invoice attached, and thirteen files that each break one rule. The rule is named in the notes. |
| `conformance/pdfua/` | 13 | A passing PDF/UA-1 control, LibreOffice's own PDF/UA export (which fails on its link), and eleven files that each break one thing; one of them, an orphaned heading, passes veraPDF 1.30. |
| `scans/` | 18 | Scanned pages made from our own documents: skew, noise, punch holes, upside down, sideways under `/Rotate`, fax resolution, CCITT G4, JBIG2, strips, mixed raster content, inverted CMYK JPEG, 16-bit, a book spread, a phone photo, a blank back page, and OCR layers that are offset, doubled or from another page. |
| `tables/` | 13 | Tables without rules, with merged cells, nested, shaded, rules only, rotated headers, right to left, financial, multi-line, drawn in text, across pages, and a spreadsheet printed across and down. |
| `languages/` | 8 | Bidirectional text, Arabic with vowels and tatweel, Urdu Nastaliq, Hebrew with niqqud, Thai and Lao, Unicode normalisation and look-alikes, invisible characters and emoji sequences, vertical Japanese with ruby, and four right-to-left pages. |
| `tools/` | 17 | Inputs for particular tools: real signatures with and without a later edit, QR separator sheets, unapplied redactions, duplicate pages, XFA, a portfolio, two hybrid-reference layouts, broken linearisation, a right-to-left booklet and a pair for compare. |

### Missing fonts

| Problem | Files |
| --- | --- |
| Simple font not embedded (TrueType or Type 1, named Arial, Garamond, Verdana and so on) | `synthetic/fonts/truetype-*`, `type1-garamond-*`, `base14-aliases` |
| No widths or wrong widths, so advances must be guessed | `truetype-no-widths-no-descriptor`, `widths-mismatch` |
| Subset tag on a font that is not embedded | `subset-tag-without-font-program`, `fonts-missing-latex/e-dvipdfmx-stripped` |
| CID font (Identity-H or -V) not embedded, with and without ToUnicode | `cid-*`, `fonts-missing-latex/f-*-stripped` |
| CJK font with a predefined CMap, not embedded | `cjk-predefined-cmap-not-embedded` |
| TeX fonts (CM, EC/cm-super, Latin Modern, URW) not embedded and without ToUnicode | `fonts-missing-latex/{b,c,g}-noembed-*` |
| Type 3 bitmap fonts with no glyph names | `fonts-missing-latex/d-pk-type3`, `synthetic/fonts/type3-unmappable` |
| Text a reader cannot recover or copy correctly | `cid-identity-not-embedded-no-tounicode`, `tounicode-lies`, `type3-unmappable` |

### Layout and structure

`synthetic/layout/` holds cases we have mistaken for tables, or edited wrongly, in
the text editor: a watermark tiled over body text, cell text running across the
grid lines, a table next to two columns of prose, a table drawn sideways, and a
highlight painted between two words of a line.

`synthetic/structure/` holds damaged files: wrong xref offsets, no xref or trailer,
a `startxref` past the end of the file, junk around the file, bare CR line endings,
a duplicated object number, an incremental update, cross-reference and object
streams, and three kinds of encryption. The 128-bit AES file opens with the
password `corpus`.

PDFium cannot open `no-xref-no-trailer.pdf`, while qpdf repairs it. `damaged-recovery/`
holds more files that only one of PDFium and PDFBox can open.

### Forms, links, metadata and hidden content

`synthetic/interactive/` holds the things page tools tend to lose: a form with
hierarchical names, a radio group, read-only, comb and calculated fields; JavaScript in
eight places; links by explicit, named and remote destinations; four-level bookmarks with
UTF-16 titles; eleven annotation types with appearance streams; a signature whose
contents are junk; and attachments with a UTF-16 name, a wrong size and a missing stream.

`synthetic/text/text-only-in-annotations.pdf` keeps all its words in annotations, and
`synthetic/content/optional-content-states.pdf` keeps the word SECRET in a layer that is
off by default. Both check that redaction, text export and blank-page detection look
beyond the page's own content stream. `synthetic/text/tagged-reading-order.pdf` draws
its right-hand column first, so only the structure tree gives the true reading order.
`synthetic/content/vector-drawing-no-text.pdf` is a bar chart and a signature stroke
with no text and no images, which blank-page detection has to render to see.

### Which files to run through which tool

| Tool | Start with |
| --- | --- |
| PDF/A conversion and validation | `conformance/pdfa/*`: each control must stay valid, each fault must be fixed or refused, and `pdfa-3b-xml-invoice-attachment` must keep its invoice |
| PDF/UA conversion and accessibility checks | `conformance/pdfua/*`, `synthetic/text/tagged-reading-order.pdf` |
| OCR | `scans/*`; the three `scan-ocr-layer-*` and `scan-double-ocr-layer` files test what skip-text and force-OCR do with an existing text layer |
| Remove blank pages | `scans/scan-blank-page-with-bleed-through.pdf` (blank, but with noise and bleed-through, so it tests the thresholds), `synthetic/content/vector-drawing-no-text.pdf` and `synthetic/text/text-only-in-annotations.pdf` (should stay) |
| Compress and greyscale | `scans/*` (CCITT, JBIG2, 16-bit, inverted CMYK), `optimizer/*` |
| PDF to CSV, Excel and Word tables | `tables/*` |
| Text extraction, search, redaction | `languages/*`, `synthetic/text/*`, `scans/scan-ocr-layer-*`, `tools/redact-annotations-not-applied.pdf` |
| Auto-split, split, merge, booklet, n-up | `tools/qr-separator-pages-auto-split.pdf`, `tools/arabic-booklet-direction-r2l.pdf`, `tools/duplicate-pages-three-copies.pdf`, `tables/table-across-pages-repeated-header.pdf` |
| Signing, sanitise, flatten | `tools/signature-*`, `tools/xfa-*`, `synthetic/interactive/*` |
| Attachments and portfolios | `tools/portfolio-collection.pdf`, `conformance/pdfa/pdfa-3b-xml-invoice-attachment.pdf`, `synthetic/interactive/attachments-unicode-and-broken.pdf` |
| Compare | `tools/compare-original.pdf` against `tools/compare-revised.pdf` |
| Repair and loading | `tools/hybrid-reference-*`, `tools/linearized-*`, `tools/page-object-listed-twice.pdf`, `damaged-recovery/*`, `synthetic/structure/*` |

## Scripts

- `scripts/make_synthetic.py OUT_DIR` rebuilds `synthetic/`, and `--list` prints
  what each file tests. It needs only the Python standard library, plus qpdf for
  the encrypted files. Apart from the AES files, which use a random salt, the
  output is byte-identical on every run.
- `scripts/latex-unembedded/build.sh` rebuilds `fonts-missing-latex/` from
  `src/*.tex`. It runs TeX Live in Docker with no network access. The stripped
  variants need an image with `pikepdf`; the script uses the Stirling-PDF image.
- `scripts/make_damaged.py SYNTHETIC_DIR OUT_DIR` writes byte mutations of the synthetic
  samples for crash and recovery testing. Each sample's mutants are seeded by its path, so
  adding samples doesn't change the existing ones.
- `scripts/rendered/make_sources.py SRC_DIR` writes the HTML and spreadsheet sources, and
  `scripts/rendered/build.sh SRC_DIR OUT_DIR IMAGE` renders them offline in Docker with
  LibreOffice and Chromium. The image must have both, plus the Liberation, DejaVu and Noto
  fonts. This builds `tables/`, `languages/`, the compare pair and the LibreOffice exports
  the next three scripts start from. Of its output, `table-*.pdf` goes in `tables/`,
  `compare-*.pdf` in `tools/`, the `lo-*.pdf` exports stay as inputs, and the rest go in
  `languages/`.
- `scripts/conformance/make_conformance.py RENDERED_DIR OUT_DIR` builds `conformance/` by
  editing the LibreOffice exports through qpdf's JSON (`pdfjson.py`).
- `scripts/scans/make_scans.py REPORT_PDF UDHR_DIR OUT_DIR` builds `scans/` with poppler,
  ImageMagick, jbig2enc and OCRmyPDF.
- `scripts/tools/make_tool_cases.py RENDERED_DIR OUT_DIR` and `scripts/tools/ToolCases.java`
  (PDFBox 3.0, BouncyCastle 1.85 and ZXing 3.5 on the classpath) build `tools/`. The
  signing key is generated and thrown away on each run.
- Unlike `make_synthetic.py`, these depend on LibreOffice, Chromium, ImageMagick and
  Tesseract, so a rebuild gives the same cases but not the same bytes.
- `scripts/build_manifest.py` writes a manifest from a notes file and the folders
  given. It uses `pdfinfo`, `pdffonts` and `qpdf` when they are installed.
- `scripts/pdfium_open.mjs DIR` opens every PDF under `DIR` with PDFium (the
  `@embedpdf/pdfium` build that Stirling-PDF's editor uses) and prints the page and
  character counts. Run it from a folder where that package is installed, such as
  Stirling-PDF's `frontend/`.

## Licence

The files we made, and the scripts, are under this repository's MIT licence. The
UDHR text is the United Nations' and may be freely reproduced. The fonts embedded
in these files keep their own licences, all of which allow them to be
redistributed embedded in a document.

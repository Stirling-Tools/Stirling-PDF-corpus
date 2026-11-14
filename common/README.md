# Common regression PDFs

A shared pool of small PDFs that break things: missing fonts, odd encodings, damaged
structure, awkward layouts. Each one should be small enough to sit in a unit or
end-to-end test and specific enough that a failure points at one cause.

## Rules for adding files

- **Licence first.** Only add a file if we made it, or its licence lets anyone
  redistribute it. Check the fonts embedded in it as well: `pdffonts file.pdf`. Don't
  add files that embed Microsoft, Apple or other commercial fonts. The fonts in this
  folder are OFL, GUST, URW (GPL with font exception), Liberation, DejaVu, Noto,
  Carlito, AMS or TeX bitmaps. Downloaded documents, customer files and bug-report
  attachments stay out. Instead, build a minimal reproduction, and add the
  generator script if you can.
- **Small.** Half the files here are under 7 KB, and none is over 310 KB. Leave out
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
| `synthetic/` | 61 | One hand-built PDF per problem, from `scripts/make_synthetic.py`, grouped into `fonts`, `text`, `layout`, `pages`, `content`, `structure` and `annotations`. |
| `fonts-missing-latex/` | 98 | The same seven LaTeX documents built 14 ways: fonts embedded, not embedded, embedded but with the font program stripped, or as Type 3 bitmaps. Each `*-embed-*` folder is the control for its `*-noembed-*` or `*-stripped` partner. |
| `latex-documents/` | 3 | Two-column reading order, hyphenation and maths, from the Office Convert benchmark. |
| `multilingual-udhr/` | 49 | One PDF per script or language (Arabic, Hebrew, the Indic scripts, CJK, Thai, Ethiopic, Tibetan, Mongolian, emoji and others), mostly Universal Declaration of Human Rights text. |
| `stirling-fixtures/` | 11 | Small generated fixtures copied from Stirling-PDF's editor tests: forms, annotations, links, tables, tagging, split content streams. |
| `optimizer/` | 18 | Filters, colour spaces, images, JPEG 2000 and structure that broke optimisation or greyscale conversion. Its own `optimizer/README.md` describes each file, and `scripts/make_optimizer_cases.py` rebuilds them. |

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

PDFium cannot open `no-xref-no-trailer.pdf`, while qpdf repairs it. That is the
one real difference between the two engines here.

## Scripts

- `scripts/make_synthetic.py OUT_DIR` rebuilds `synthetic/`, and `--list` prints
  what each file tests. It needs only the Python standard library, plus qpdf for
  the encrypted files. Apart from the AES files, which use a random salt, the
  output is byte-identical on every run.
- `scripts/latex-unembedded/build.sh` rebuilds `fonts-missing-latex/` from
  `src/*.tex`. It runs TeX Live in Docker with no network access. The stripped
  variants need an image with `pikepdf`; the script uses the Stirling-PDF image.
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

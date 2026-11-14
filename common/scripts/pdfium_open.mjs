// Opens every PDF under a folder with PDFium and prints "<path>\tpages=N\tchars=N" or "<path>\tERR <code>".
// Usage, from a folder with @embedpdf/pdfium installed: node pdfium_open.mjs DIR

import { readFile, readdir } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
const require = createRequire(process.cwd() + "/package.json");
const { init } = await import(require.resolve("@embedpdf/pdfium"));
const wasm = await readFile(require.resolve("@embedpdf/pdfium/pdfium.wasm"));
const m = await init({ wasmBinary: wasm });
m.PDFiumExt_Init();
async function* walk(d) { for (const e of await readdir(d, { withFileTypes: true })) { const p = path.join(d, e.name); if (e.isDirectory()) yield* walk(p); else if (p.endsWith(".pdf")) yield p; } }
for await (const f of walk(process.argv[2])) {
  const bytes = await readFile(f);
  const ptr = m.pdfium.wasmExports.malloc(bytes.length); m.pdfium.HEAPU8.set(bytes, ptr);
  const doc = m.FPDF_LoadMemDocument(ptr, bytes.length, "");
  if (!doc) { console.log(`${path.relative(process.argv[2], f)}\tERR ${m.FPDF_GetLastError()}`); m.pdfium.wasmExports.free(ptr); continue; }
  const n = m.FPDF_GetPageCount(doc); let chars = 0;
  for (let i = 0; i < n; i++) { const p = m.FPDF_LoadPage(doc, i); const t = m.FPDFText_LoadPage(p); chars += m.FPDFText_CountChars(t); m.FPDFText_ClosePage(t); m.FPDF_ClosePage(p); }
  console.log(`${path.relative(process.argv[2], f)}\tpages=${n}\tchars=${chars}`);
  m.FPDF_CloseDocument(doc); m.pdfium.wasmExports.free(ptr);
}

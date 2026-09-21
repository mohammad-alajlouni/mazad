// npm install --prefix <tools-dir> mtx-decompressor@1.6.0
// node this-script.mjs <tools-dir>/node_modules/mtx-decompressor/dist/index.js <extracted-font-dir>
// Extract ppt/fonts/font{5..10}.fntdata from the source PPTX to that directory first.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const { eotToTtf } = await import(pathToFileURL(path.resolve(process.argv[2])).href);
const dir = process.argv[3];
for (const n of [5, 6, 7, 8, 9, 10]) {
  fs.writeFileSync(path.join(dir, `font${n}.ttf`), eotToTtf(fs.readFileSync(path.join(dir, `font${n}.fntdata`))));
}

# Infath identity source

`infath-identity.pptx` is an unchanged copy of the user-supplied
`الالوان-والخط-والايقوناتت-للتصميم.pptx`. The generated asset manifest records its SHA-256.

## Reference decisions

- Slide 2 has conflicting written hexadecimal labels (including `243866` repeated
  under four different swatches). Dynamic template colors use **actual shape
  fills**, not those labels. This interpretation was disclosed to the user;
  it is not a declaration that the conflicting labels have official approval.
- The 252 icons on slide 5 are native DrawingML geometry. The extractor preserves
  all paths, group transforms, fills, strokes and proportions. Selected clock,
  calendar, location, platform and phone icons were visually identified on the
  source sheet. Their native `01355A` / `17A3A3` colors are not recolored to match
  the palette. White backgrounds behind small icons preserve their legibility
  on dark templates.
- Slide 1's EMF objects contain original vector PDFs. The logo SVGs retain the
  painted paths; a redundant page-sized clipping wrapper is removed to avoid
  an HTML renderer clipping bug. No bitmap tracing or replacement logo is used.
- Embedded font streams provide Ruaq Light/Medium/Bold and Lama Sans
  Light/Medium/**Black**. Body weight 400 selects the original Light face;
  English bold headings select actual Black, not synthesized Bold.
- Slide 3/4's 24/14 typography samples specify hierarchy. Dimensions and sizes
  particular to each supplied booklet/banner/social layout remain controlled by
  their existing templates. Original static booklet covers/introduction/terms
  and participation artwork remain intact from their own source PDFs.

## Reproducing assets

Use the repository Python environment (PyMuPDF) and Node. Install the development
converter outside application dependencies:

```sh
npm install --prefix tmp/design-font-tools --ignore-scripts mtx-decompressor@1.6.0
```

Extract `ppt/fonts/font5.fntdata` through `font10.fntdata` from the source ZIP into
one temporary directory, then run:

```sh
node backend/scripts/decompress_identity_fonts.mjs tmp/design-font-tools/node_modules/mtx-decompressor/dist/index.js tmp/extracted-fonts
backend/.venv/bin/python backend/scripts/extract_identity_pptx.py backend/design_sources/infath-identity.pptx tmp/extracted-fonts
```

MTX conversion uses [mtx-decompressor 1.6.0](https://github.com/ChristopherVR/mtx-decompressor).
Only the supplied embedded fonts are decoded; no substitute fonts are downloaded.

## Verification and limits

`test_identity.py` checks source/asset hashes, every icon's path coordinates,
actual PowerPoint palette fills, and font embedding without system substitution.
The existing generation tests cover output dimensions, page count, text bounds,
booklet live-preview/export parity, and all auction types. Social pixel checks
also catch invisible logos/text after SVG painting.

These are asset-integrity and rendering checks. They **do not certify pixel-perfect
conformance of every composed page or official approval**. Variable data, text
lengths, and the palette-label discrepancy still require comparison of final
publication outputs with the applicable approved layout. Existing preflight
continues rejecting overflowing content instead of shrinking official dimensions.

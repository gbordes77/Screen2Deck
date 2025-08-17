# Architecture

```
[Webapp (Next.js)] --HTTP--> [Backend (FastAPI)]
                                   |
                                   |  OCR + Parsing + Matching
                                   v
                          [Preprocess (OpenCV)]
                                   |
                                EasyOCR
                             (Vision Fallback*)
                                   |
                          [Parse qty + name + SB]
                                   |
                          [Fuzzy + Scryfall cache]
                                   |
                      [ALWAYS verify via Scryfall]
                 (offline exact/fuzzy -> online fallback)
                                   |
                          [Normalized deck + IDs]
                                   |
                              [Export formats]
```

- **No Tesseract** (explicitly out).
- **EasyOCR primary**, Vision-OCR fallback via flag.
- **ALWAYS** canonicalize each recognized name with **Scryfall** (`name`, `scryfall_id`).

## Data model
- `RawOCR` → spans (`text`, `conf`), `mean_conf`
- `DeckSections` → `main[]`, `side[]` with (`qty`, `name`, `candidates[]`)
- `NormalizedDeck` → canonical (`name`, `scryfall_id`, `qty`) split into main/side

# Screen2Deck – Mini Brand Kit

**Tagline (EN)**: From screenshot to perfect decklist.  
**Tagline (FR)**: OCR → Decklist validée.

## Core Assets
- Icon PNGs: 16, 32, 180, 512, 1024
- Icon SVG: `s2d_icon.svg`
- Wordmark SVG: `s2d_wordmark.svg`
- Social banner PNG: 1500×500
- Favicon SVG + PNGs
- Web `manifest.json` (PWA-ready)

## Colors
- Primary: #6D28D9
- Accent:  #22D3EE
- Dark:    #0B1021
- Light:   #F7F7FB

## Typography
- Sans-serif: **Inter** or **Manrope** (fallback: system-ui).  
  Use **Bold/ExtraBold** for titles, **Regular/Medium** for body.

## Logo Usage
- Clear space: at least the height of the “2” around the icon/wordmark.
- Minimum sizes:  
  - Icon: 16px (favicon), 32px (UI), 180px (touch).  
  - Wordmark: ≥ 24px height for readability.
- Backgrounds:  
  - Dark or primary backgrounds → use **light** icon.  
  - Light backgrounds → default icon.
- Don’ts:  
  - Don’t alter colors, distort, or add effects.  
  - Don’t rotate card shapes or edit “S2D” text.  
  - Don’t place on low-contrast imagery.

## Product Lockups
Prefer “Screen2Deck” wordmark + tagline EN (global) or FR (local) on landing pages and store listings.

## Export/Dev Notes
- Favicon: use `favicon.svg` for modern browsers; provide 32/16 PNGs as fallbacks; Apple touch uses 180 PNG.
- PWA: `manifest.json` includes icons and theme colors.
- Accessibility: keep contrast ≥ 4.5:1 for body text; accent on dark is compliant.

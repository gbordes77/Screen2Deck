# FAQ

**Q: Can we use Tesseract?**  
A: No. It's explicitly excluded.

**Q: Do we always call Scryfall?**  
A: Yes. Every card name is canonicalized via Scryfall (offline first, online fallback if enabled).

**Q: GPU required?**  
A: No. CPU-only target.

**Q: How to improve tough photos?**  
A: Turn on `ENABLE_VISION_FALLBACK=true` and consider higher `OCR_MIN_LINES` threshold.

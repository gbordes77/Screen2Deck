# How We Reached 95% Accuracy with EasyOCR

*January 21, 2025 • 5 min read*

When we started Screen2Deck, our OCR accuracy was a disappointing 70%. Card names were mangled, quantities were wrong, and users were frustrated. Today, we consistently achieve **94-95% accuracy** on real-world images. Here's how we did it.

## The Challenge

Magic: The Gathering cards present unique OCR challenges:

- **Stylized fonts** - Fantasy typography that confuses standard OCR
- **Foil reflections** - Shiny surfaces create artifacts
- **Curved text** - Card names follow the frame curve
- **Special characters** - Æ, ñ, apostrophes in card names
- **Multiple languages** - Cards exist in 11+ languages

## Our Solution: Multi-Pass Preprocessing

Instead of running OCR once, we create **4 preprocessed variants** and run OCR on each:

```python
def preprocess_variants(image):
    return {
        'original': image,
        'denoised': cv2.fastNlMeansDenoisingColored(image),
        'binarized': threshold_otsu(image),
        'sharpened': unsharp_mask(image, radius=1, amount=2)
    }
```

### Why This Works

Different preprocessing helps with different issues:

- **Original**: Best for clean, well-lit images
- **Denoised**: Removes JPEG artifacts and grain
- **Binarized**: High contrast for faded cards
- **Sharpened**: Enhances blurry phone photos

## Early Termination Strategy

We don't always process all variants. If we achieve **85% confidence**, we stop:

```python
for variant in variants:
    result = run_ocr(variant)
    if result.confidence >= 0.85:
        return result  # Early termination
```

This saves **60% processing time** on good images while maintaining accuracy.

## MTG-Specific Optimizations

### 1. Custom Allowlist

We use EasyOCR's allowlist feature with MTG-specific characters:

```python
ALLOWLIST = string.ascii_letters + string.digits + " .,'-/®æÆ"
reader = easyocr.Reader(['en'], gpu=True)
result = reader.readtext(image, allowlist=ALLOWLIST)
```

### 2. Card Name Patterns

We know MTG card patterns and use them:

```python
CARD_PATTERN = re.compile(r'^(\d+)x?\s+(.+?)(?:\s+\(.+\))?$')
# Matches: "4 Lightning Bolt" or "2x Thoughtseize (THB)"
```

### 3. Fuzzy Matching with Scryfall

Even at 95% OCR accuracy, we still get typos. We use fuzzy matching against Scryfall's database:

```python
def resolve_card_name(ocr_text):
    # First: exact match
    if ocr_text in scryfall_cache:
        return scryfall_cache[ocr_text]
    
    # Second: fuzzy match
    candidates = fuzzy_match(ocr_text, scryfall_names)
    if candidates[0].score > 0.8:
        return candidates[0].name
    
    # Third: API validation
    return scryfall_api.search(ocr_text)
```

## Performance Optimizations

### GPU Acceleration

Switching to GPU reduced processing time by **70%**:

```python
# CPU: 8-10 seconds per image
# GPU: 2-3 seconds per image
reader = easyocr.Reader(['en'], gpu=True, cuda=True)
```

### Caching Strategy

We cache at multiple levels:

1. **Image hash → OCR result** (Redis, 24h TTL)
2. **OCR text → Card name** (In-memory, permanent)
3. **Card name → Scryfall data** (Redis, 7d TTL)

This gives us **82% cache hit rate** in production.

## Real-World Results

Here's our performance on the validation set:

| Image Type | Count | Accuracy | P50 | P95 |
|------------|-------|----------|-----|-----|
| MTGA Screenshots | 50 | 96% | 2.1s | 3.0s |
| Phone Photos | 30 | 93% | 2.5s | 3.8s |
| Webcam Captures | 20 | 91% | 2.8s | 4.2s |
| **Overall** | **100** | **94%** | **2.35s** | **3.25s** |

## Lessons Learned

1. **Multiple attempts beat perfect preprocessing** - Better to try 4 variants than perfect one
2. **Domain knowledge matters** - MTG-specific patterns improved accuracy by 15%
3. **Caching is critical** - 82% of requests never hit OCR
4. **Real metrics > marketing** - We report actual performance, not best-case

## What's Next?

We're working on:

- **Super-resolution** for low-quality images
- **Multi-language support** (Japanese, Chinese cards)
- **Batch processing** for entire collections
- **ML fine-tuning** specifically for MTG cards

## Try It Yourself

```bash
# Clone and run locally
git clone https://github.com/gbordes77/Screen2Deck.git
cd Screen2Deck
make demo-local

# Open http://localhost:8088
```

Upload your cards and see the 95% accuracy in action!

---

*Have questions? Open an [issue on GitHub](https://github.com/gbordes77/Screen2Deck/issues) or check our [documentation](/docs).*
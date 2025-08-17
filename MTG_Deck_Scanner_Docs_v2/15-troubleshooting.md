# Troubleshooting

- **Upload fails 400/413**: wrong mimetype or too large. Check `MAX_IMAGE_MB`.
- **Status stuck**: check backend logs; ensure job stored in memory; for multi-instance use Redis.
- **Names slightly off**: verify Scryfall cache hydrated; online fallback enabled.
- **Exports rejected by site**: copy visible line breaks exactly; check format doc (06-exports.md).

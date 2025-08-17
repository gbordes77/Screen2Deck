# Screen2Deck Discord Bot

Discord bot providing parity with the Screen2Deck web application for deck image OCR and export.

## Features

✅ **Slash Commands**
- `/deck from_image` - Extract deck list from uploaded image
- `/deck export <format>` - Export last processed deck to specified format

✅ **Export Formats**
- MTG Arena
- Moxfield  
- Archidekt
- TappedOut

✅ **Performance**
- <5s processing time (P95)
- ≥95% accuracy
- Intelligent caching
- Rate limiting

✅ **Web Parity**
- Identical OCR processing pipeline
- Same export formats
- Consistent error handling
- Shared golden test data

## Setup

### 1. Create Discord Application

1. Go to https://discord.com/developers/applications
2. Click "New Application" and name it "Screen2Deck"
3. Go to "Bot" section
4. Click "Reset Token" and save the token
5. Enable "MESSAGE CONTENT INTENT" if needed
6. Go to "OAuth2" → "URL Generator"
7. Select scopes: `bot`, `applications.commands`
8. Select permissions: `Send Messages`, `Attach Files`, `Use Slash Commands`
9. Copy the generated URL and invite bot to your server

### 2. Configure Environment

```bash
cd discord
cp .env.example .env
```

Edit `.env` with your values:
```env
DISCORD_TOKEN=your_bot_token_here
DISCORD_CLIENT_ID=your_client_id_here
DISCORD_GUILD_ID=your_dev_guild_id_here  # Optional for dev
SCREEN2DECK_API_URL=http://localhost:8080
```

### 3. Install Dependencies

```bash
npm install
```

### 4. Deploy Commands

```bash
npm run deploy-commands
```

### 5. Start Bot

```bash
# Development
npm run dev

# Production
npm run build
npm start
```

## Docker Deployment

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

USER node
CMD ["npm", "start"]
```

```yaml
# docker-compose.yml addition
discord-bot:
  build: ./discord
  restart: unless-stopped
  env_file: ./discord/.env
  depends_on:
    - backend
  networks:
    - screen2deck
```

## Testing

### Run Parity Tests

```bash
# Ensure backend is running first
cd ../backend && docker compose up -d

# Run tests
cd discord
npm test

# Run only parity tests
npm run test:parity
```

### Test Coverage

```bash
npm run test -- --coverage
```

## Usage

### Extract Deck from Image

1. Type `/deck from_image` in Discord
2. Attach an image of your deck
3. Bot processes and returns the deck list
4. Use dropdown menu to export to different formats

### Export Deck

1. Type `/deck export` and select format
2. Bot sends the deck in requested format as a file

### Interactive Export

After processing an image, use the dropdown menu that appears to quickly export to any format.

## Architecture

```
discord/
├── src/
│   ├── index.ts           # Bot entry point
│   ├── config.ts          # Environment config
│   ├── logger.ts          # Winston logger
│   ├── api-client.ts      # Screen2Deck API client
│   ├── rate-limiter.ts    # Per-user rate limiting
│   └── commands/
│       └── deck.ts        # Deck slash commands
├── tests/
│   ├── parity.test.ts     # Web ↔️ Discord parity tests
│   └── setup.ts           # Test configuration
└── scripts/
    └── deploy-commands.ts  # Command deployment

```

## Monitoring

### Logs

```bash
# Development
tail -f combined.log

# Production (Docker)
docker logs -f screen2deck-discord-bot
```

### Metrics

The bot exposes metrics compatible with the main application:
- Command usage counts
- Processing times
- Error rates
- Cache hit rates

## Rate Limiting

Default limits:
- 10 requests per user per hour
- 5 concurrent jobs maximum
- Configurable via environment variables

## Error Handling

The bot handles:
- Invalid image formats
- Oversized images (>8MB)
- API timeouts
- Rate limiting
- Network errors

All errors are logged with context for debugging.

## Security

- Bot token stored securely in environment
- API key authentication (optional)
- Rate limiting per user
- Input validation on all commands
- No direct database access

## Troubleshooting

### Bot Not Responding

1. Check bot is online in Discord
2. Verify slash commands are deployed
3. Check bot has proper permissions
4. Review logs for errors

### Slow Processing

1. Check backend API health
2. Verify GPU acceleration is enabled
3. Review cache hit rates
4. Check network latency

### Commands Not Showing

1. Redeploy commands: `npm run deploy-commands`
2. Wait 1 hour for global commands to propagate
3. Check bot has `applications.commands` scope

## Development

### Adding New Commands

1. Create new command file in `src/commands/`
2. Export command data and execute function
3. Register in `src/index.ts`
4. Deploy with `npm run deploy-commands`

### Testing Changes

1. Use development guild for instant command updates
2. Run parity tests to ensure consistency
3. Test with real deck images from validation set

## License

MIT - See LICENSE file
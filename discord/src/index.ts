import { Client, GatewayIntentBits, Events, Collection } from 'discord.js';
import { config } from './config';
import { logger } from './logger';
import { deckCommand, handleExportMenu } from './commands/deck';
import { Screen2DeckAPIClient } from './api-client';

// Create Discord client
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages
  ]
});

// Command collection
const commands = new Collection<string, any>();
commands.set(deckCommand.data.name, deckCommand);

// Ready event
client.once(Events.ClientReady, async (c) => {
  logger.info(`Discord bot ready! Logged in as ${c.user.tag}`);
  
  // Set activity
  c.user.setActivity('deck images', { type: 3 }); // Type 3 = Watching
  
  // Check API health
  const apiClient = new Screen2DeckAPIClient();
  const apiHealthy = await apiClient.health();
  
  if (!apiHealthy) {
    logger.error('Screen2Deck API is not healthy!');
  } else {
    logger.info('Screen2Deck API connection verified');
  }
});

// Interaction handler
client.on(Events.InteractionCreate, async (interaction) => {
  try {
    // Handle slash commands
    if (interaction.isChatInputCommand()) {
      const command = commands.get(interaction.commandName);
      
      if (!command) {
        logger.warn(`Unknown command: ${interaction.commandName}`);
        return;
      }
      
      await command.execute(interaction);
    }
    
    // Handle select menu interactions
    else if (interaction.isStringSelectMenu()) {
      if (interaction.customId === 'export_format') {
        await handleExportMenu(interaction);
      }
    }
  } catch (error) {
    logger.error('Error handling interaction', { error });
    
    const reply = {
      content: '❌ An error occurred while processing your request.',
      ephemeral: true
    };
    
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp(reply);
    } else {
      await interaction.reply(reply);
    }
  }
});

// Error handling
client.on(Events.Error, (error) => {
  logger.error('Discord client error', { error });
});

client.on(Events.Warn, (warning) => {
  logger.warn('Discord client warning', { warning });
});

// Graceful shutdown
process.on('SIGINT', () => {
  logger.info('Shutting down Discord bot...');
  client.destroy();
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Shutting down Discord bot...');
  client.destroy();
  process.exit(0);
});

// Start the bot
client.login(config.discordToken).catch((error) => {
  logger.error('Failed to login to Discord', { error });
  process.exit(1);
});
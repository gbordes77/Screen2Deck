import { REST, Routes } from 'discord.js';
import { config } from '../src/config';
import { deckCommand } from '../src/commands/deck';
import { logger } from '../src/logger';

const commands = [deckCommand.data.toJSON()];

const rest = new REST({ version: '10' }).setToken(config.discordToken);

async function deployCommands() {
  try {
    logger.info(`Started refreshing ${commands.length} application (/) commands.`);
    
    let data: any;
    
    // Deploy to specific guild in development
    if (config.guildId && config.nodeEnv === 'development') {
      data = await rest.put(
        Routes.applicationGuildCommands(config.clientId, config.guildId),
        { body: commands }
      );
      logger.info(`Successfully reloaded ${data.length} guild commands.`);
    } 
    // Deploy globally in production
    else {
      data = await rest.put(
        Routes.applicationCommands(config.clientId),
        { body: commands }
      );
      logger.info(`Successfully reloaded ${data.length} global commands.`);
    }
    
  } catch (error) {
    logger.error('Error deploying commands', { error });
    process.exit(1);
  }
}

deployCommands();
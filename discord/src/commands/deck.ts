import {
  SlashCommandBuilder,
  CommandInteraction,
  AttachmentBuilder,
  EmbedBuilder,
  ActionRowBuilder,
  StringSelectMenuBuilder,
  StringSelectMenuInteraction
} from 'discord.js';
import { Screen2DeckAPIClient } from '../api-client';
import { logger } from '../logger';
import { RateLimiter } from '../rate-limiter';
import NodeCache from 'node-cache';
import { config } from '../config';

const apiClient = new Screen2DeckAPIClient();
const rateLimiter = new RateLimiter();
const cache = new NodeCache({ stdTTL: config.cacheTTL });

export const deckCommand = {
  data: new SlashCommandBuilder()
    .setName('deck')
    .setDescription('Convert deck images to various formats')
    .addSubcommand(subcommand =>
      subcommand
        .setName('from_image')
        .setDescription('Extract deck list from an image')
        .addAttachmentOption(option =>
          option
            .setName('image')
            .setDescription('The deck image to process')
            .setRequired(true)
        )
    )
    .addSubcommand(subcommand =>
      subcommand
        .setName('export')
        .setDescription('Export last processed deck to a specific format')
        .addStringOption(option =>
          option
            .setName('format')
            .setDescription('Export format')
            .setRequired(true)
            .addChoices(
              { name: 'MTG Arena', value: 'mtga' },
              { name: 'Moxfield', value: 'moxfield' },
              { name: 'Archidekt', value: 'archidekt' },
              { name: 'TappedOut', value: 'tappedout' }
            )
        )
    ),
  
  async execute(interaction: CommandInteraction) {
    const subcommand = interaction.options.getSubcommand();
    
    if (subcommand === 'from_image') {
      await handleFromImage(interaction);
    } else if (subcommand === 'export') {
      await handleExport(interaction);
    }
  }
};

async function handleFromImage(interaction: CommandInteraction) {
  // Check rate limit
  const userId = interaction.user.id;
  if (!rateLimiter.checkLimit(userId)) {
    await interaction.reply({
      content: '⏳ You\'ve reached the rate limit. Please wait before submitting another image.',
      ephemeral: true
    });
    return;
  }
  
  // Get attachment
  const attachment = interaction.options.getAttachment('image', true);
  
  // Validate image
  if (!attachment.contentType?.startsWith('image/')) {
    await interaction.reply({
      content: '❌ Please provide a valid image file.',
      ephemeral: true
    });
    return;
  }
  
  if (attachment.size > 8 * 1024 * 1024) {  // 8MB limit
    await interaction.reply({
      content: '❌ Image is too large. Maximum size is 8MB.',
      ephemeral: true
    });
    return;
  }
  
  // Defer reply as this will take time
  await interaction.deferReply();
  
  try {
    // Download image
    const response = await fetch(attachment.url);
    const buffer = Buffer.from(await response.arrayBuffer());
    
    // Check cache
    const cacheKey = `ocr_${attachment.id}`;
    const cachedResult = cache.get(cacheKey);
    if (cachedResult) {
      logger.info('Using cached OCR result', { attachmentId: attachment.id });
      await sendDeckResult(interaction, cachedResult as any, true);
      return;
    }
    
    // Upload to API
    logger.info('Uploading image to API', { 
      userId,
      attachmentId: attachment.id,
      size: attachment.size 
    });
    
    const jobId = await apiClient.uploadImage(buffer, attachment.name);
    
    // Wait for completion
    const result = await apiClient.waitForCompletion(jobId, 30000);
    
    if (result.status === 'failed') {
      throw new Error(result.error || 'OCR processing failed');
    }
    
    // Cache result
    cache.set(cacheKey, result);
    cache.set(`user_last_deck_${userId}`, result);
    
    // Send result
    await sendDeckResult(interaction, result, false);
    
  } catch (error) {
    logger.error('Error processing image', { error, userId });
    
    await interaction.editReply({
      content: '❌ Failed to process the image. Please try again later.',
    });
  }
}

async function sendDeckResult(
  interaction: CommandInteraction,
  result: any,
  fromCache: boolean
) {
  const { mainboard, sideboard, metadata } = result.result;
  
  // Calculate total cards
  const mainboardTotal = mainboard.reduce((sum: number, card: any) => sum + card.qty, 0);
  const sideboardTotal = sideboard?.reduce((sum: number, card: any) => sum + card.qty, 0) || 0;
  
  // Create embed
  const embed = new EmbedBuilder()
    .setTitle('📋 Deck List Extracted')
    .setColor(0x00AE86)
    .setTimestamp()
    .setFooter({ 
      text: fromCache ? 'From cache' : 'Processed',
      iconURL: interaction.client.user?.displayAvatarURL()
    });
  
  // Add mainboard
  let mainboardText = mainboard
    .slice(0, 15)  // Limit to prevent embed from being too large
    .map((card: any) => `${card.qty}x ${card.name}`)
    .join('\n');
  
  if (mainboard.length > 15) {
    mainboardText += `\n... and ${mainboard.length - 15} more`;
  }
  
  embed.addFields({
    name: `Mainboard (${mainboardTotal} cards)`,
    value: mainboardText || 'No cards found',
    inline: false
  });
  
  // Add sideboard if present
  if (sideboard && sideboard.length > 0) {
    const sideboardText = sideboard
      .map((card: any) => `${card.qty}x ${card.name}`)
      .join('\n');
    
    embed.addFields({
      name: `Sideboard (${sideboardTotal} cards)`,
      value: sideboardText,
      inline: false
    });
  }
  
  // Add metadata
  if (metadata) {
    embed.addFields({
      name: 'Processing Info',
      value: [
        `⚡ Time: ${(metadata.processingTime / 1000).toFixed(2)}s`,
        `🎯 Confidence: ${(metadata.confidence * 100).toFixed(1)}%`,
        `🤖 Vision API: ${metadata.usedVisionFallback ? 'Yes' : 'No'}`
      ].join('\n'),
      inline: true
    });
  }
  
  // Create export menu
  const row = new ActionRowBuilder<StringSelectMenuBuilder>()
    .addComponents(
      new StringSelectMenuBuilder()
        .setCustomId('export_format')
        .setPlaceholder('Export deck to...')
        .addOptions([
          {
            label: 'MTG Arena',
            description: 'Export for MTG Arena import',
            value: 'mtga',
            emoji: '🎮'
          },
          {
            label: 'Moxfield',
            description: 'Export for Moxfield.com',
            value: 'moxfield',
            emoji: '📚'
          },
          {
            label: 'Archidekt',
            description: 'Export for Archidekt.com',
            value: 'archidekt',
            emoji: '🏛️'
          },
          {
            label: 'TappedOut',
            description: 'Export for TappedOut.net',
            value: 'tappedout',
            emoji: '📝'
          }
        ])
    );
  
  await interaction.editReply({
    embeds: [embed],
    components: [row]
  });
}

async function handleExport(interaction: CommandInteraction) {
  const userId = interaction.user.id;
  const format = interaction.options.getString('format', true) as any;
  
  // Get last deck from cache
  const lastDeck = cache.get(`user_last_deck_${userId}`);
  
  if (!lastDeck) {
    await interaction.reply({
      content: '❌ No deck found. Please use `/deck from_image` first.',
      ephemeral: true
    });
    return;
  }
  
  await interaction.deferReply();
  
  try {
    const deckData = (lastDeck as any).result;
    
    // Export deck
    const exportContent = await apiClient.exportDeck({
      format,
      mainboard: deckData.mainboard,
      sideboard: deckData.sideboard,
      deckName: `Discord Export ${new Date().toISOString()}`
    });
    
    // Create file attachment
    const attachment = new AttachmentBuilder(
      Buffer.from(exportContent),
      { name: `deck_export.${format === 'mtga' ? 'txt' : format}` }
    );
    
    // Create response embed
    const embed = new EmbedBuilder()
      .setTitle(`📤 Exported to ${format.toUpperCase()}`)
      .setColor(0x00AE86)
      .setDescription('Your deck has been exported successfully!')
      .setTimestamp()
      .setFooter({ 
        text: `Format: ${format}`,
        iconURL: interaction.client.user?.displayAvatarURL()
      });
    
    await interaction.editReply({
      embeds: [embed],
      files: [attachment]
    });
    
  } catch (error) {
    logger.error('Error exporting deck', { error, userId, format });
    
    await interaction.editReply({
      content: '❌ Failed to export deck. Please try again later.'
    });
  }
}

// Handle select menu interactions
export async function handleExportMenu(interaction: StringSelectMenuInteraction) {
  const format = interaction.values[0] as any;
  const userId = interaction.user.id;
  
  // Get last deck from cache
  const lastDeck = cache.get(`user_last_deck_${userId}`);
  
  if (!lastDeck) {
    await interaction.reply({
      content: '❌ Deck data expired. Please process the image again.',
      ephemeral: true
    });
    return;
  }
  
  await interaction.deferReply({ ephemeral: true });
  
  try {
    const deckData = (lastDeck as any).result;
    
    // Export deck
    const exportContent = await apiClient.exportDeck({
      format,
      mainboard: deckData.mainboard,
      sideboard: deckData.sideboard,
      deckName: `Discord Export ${new Date().toISOString()}`
    });
    
    // Create file attachment
    const attachment = new AttachmentBuilder(
      Buffer.from(exportContent),
      { name: `deck_export.${format === 'mtga' ? 'txt' : format}` }
    );
    
    await interaction.editReply({
      content: `✅ Exported to ${format.toUpperCase()}`,
      files: [attachment]
    });
    
  } catch (error) {
    logger.error('Error in export menu', { error, userId, format });
    
    await interaction.editReply({
      content: '❌ Failed to export deck. Please try again.'
    });
  }
}
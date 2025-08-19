// tests/webapp.smoke.js
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const FRONT_URL = process.env.FRONT_URL || 'http://localhost:3000';
  const CANDIDATE_IMAGES = [
    'validation_set/images/MTGA deck list_1535x728.jpeg',
    'validation_set/images/MTGA deck list special_1334x886.jpeg',
    'validation_set/images/MTGO deck list usual_1763x791.jpeg'
  ];
  const imagePath = CANDIDATE_IMAGES.find(p => fs.existsSync(p));
  if (!imagePath) throw new Error('Aucune image trouvée dans validation_set/.');

  console.log('🎯 Test Playwright Smoke');
  console.log('📂 Image sélectionnée:', imagePath);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.setDefaultTimeout(60000);

  try {
    console.log('➡️  Ouverture UI:', FRONT_URL);
    await page.goto(FRONT_URL, { waitUntil: 'domcontentloaded' });

    // Vérifier que la page a chargé
    await page.waitForSelector('h1:has-text("MTG Deck Scanner")', { timeout: 10000 });
    console.log('✓ Page chargée');

    // Trouver et utiliser l'input file
    const input = page.locator('input[type="file"]');
    if ((await input.count()) === 0) {
      throw new Error("Input d'upload introuvable.");
    }

    console.log('📸 Upload de l\'image...');
    await input.setInputFiles(imagePath);

    // Attendre un peu pour que le fichier soit chargé
    await page.waitForTimeout(1000);

    // Vérifier que le fichier est sélectionné (plusieurs façons possibles)
    const fileSelected = await page.locator('text=/Selected:|' + imagePath.split('/').pop() + '/i').count() > 0 ||
                        await page.locator('text=/' + imagePath.split('/').pop() + '/i').count() > 0;
    
    if (fileSelected) {
      console.log('✓ Fichier sélectionné');
    }

    // Cliquer sur le bouton "Process" ou équivalent (peut être en français)
    const processButton = page.locator('button:has-text("Process"), button:has-text("Upload"), button:has-text("Scan"), button:has-text("Submit"), button:has-text("Analyser"), button:has-text("Analyze")').first();
    if ((await processButton.count()) === 0) {
      throw new Error("Bouton de traitement introuvable (Process/Upload/Scan/Submit/Analyser).");
    }
    
    const buttonText = await processButton.textContent();
    console.log(`🔄 Clic sur "${buttonText}"...`);
    await processButton.click();

    // Attendre la navigation vers /result/[jobId]
    await page.waitForURL('**/result/**', { timeout: 30000 });
    console.log('✓ Redirection vers la page de résultats');

    // Attendre que le traitement se termine
    // On cherche soit du texte de deck, soit des boutons d'export
    const resultIndicators = [
      'text=/\\d+\\s+(Island|Forest|Mountain|Plains|Swamp)/i',  // Cartes de base
      'text=/Mainboard/i',
      'text=/Sideboard/i',
      'button:has-text("Export")',
      'text=/Export.*MTGA/i',
      'pre',  // Block de code avec le deck
      'text=/\\d+\\s+\\w+/i'  // Pattern générique pour les cartes
    ];

    console.log('⏳ Attente du résultat OCR...');
    let resultFound = false;
    
    for (const selector of resultIndicators) {
      try {
        await page.waitForSelector(selector, { timeout: 30000 });
        resultFound = true;
        console.log(`✓ Résultat trouvé via: ${selector}`);
        break;
      } catch {
        // Continue avec le prochain sélecteur
      }
    }

    if (!resultFound) {
      // Dernière tentative : vérifier le contenu de la page
      await page.waitForTimeout(5000);
      const pageText = await page.textContent('body');
      
      // Vérifier si on a des noms de cartes Magic
      const magicCards = ['Island', 'Forest', 'Mountain', 'Plains', 'Swamp', 
                          'Lightning Bolt', 'Counterspell', 'Llanowar Elves'];
      const hasCards = magicCards.some(card => pageText?.includes(card));
      
      if (hasCards) {
        resultFound = true;
        console.log('✓ Contenu de deck détecté dans la page');
      }
    }

    if (!resultFound) {
      throw new Error('Aucun résultat OCR détecté après 30 secondes');
    }

    // Vérifier si on peut exporter (optionnel mais bon indicateur)
    const exportButtons = await page.locator('button:has-text("Export")').count();
    if (exportButtons > 0) {
      console.log(`✓ ${exportButtons} bouton(s) d'export disponible(s)`);
    }

    // Essayer de récupérer un aperçu du deck
    try {
      const preElement = await page.locator('pre').first();
      if (await preElement.count() > 0) {
        const deckText = await preElement.textContent();
        if (deckText && deckText.trim().length > 10) {
          const preview = deckText.split('\n').slice(0, 3).join('\n');
          console.log('📋 Aperçu du deck:');
          console.log(preview);
          if (deckText.split('\n').length > 3) {
            console.log('   ...');
          }
        }
      }
    } catch {
      // Pas grave si on ne peut pas afficher l'aperçu
    }

    console.log('\n✅ PASS — Upload réussi, OCR traité, résultat affiché!');
    await browser.close();
    process.exit(0);

  } catch (e) {
    console.error('\n❌ FAIL —', e.message);
    
    // Capturer plus d'infos pour le debug
    try {
      const url = page.url();
      console.error('📍 URL actuelle:', url);
      
      const pageTitle = await page.title();
      console.error('📄 Titre de la page:', pageTitle);
      
      // Essayer de capturer les erreurs dans la console
      page.on('console', msg => {
        if (msg.type() === 'error') {
          console.error('🔴 Erreur console:', msg.text());
        }
      });
    } catch {}
    
    await page.screenshot({ path: 'tests/last_error.png', fullPage: true });
    console.error('📸 Screenshot sauvé dans tests/last_error.png');
    
    await browser.close();
    process.exit(1);
  }
})();
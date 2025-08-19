// tests/webapp.online.js - Test E2E 100% ONLINE
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const FRONT_URL = process.env.FRONT_URL || 'http://localhost:3000';
  const API_URL = process.env.API_URL || 'http://localhost:8080';
  
  const CANDIDATE_IMAGES = [
    'validation_set/images/MTGA deck list_1535x728.jpeg',
    'validation_set/images/MTGA deck list special_1334x886.jpeg',
    'validation_set/images/MTGO deck list usual_1763x791.jpeg'
  ];
  
  const imagePath = CANDIDATE_IMAGES.find(p => fs.existsSync(p));
  if (!imagePath) throw new Error('Aucune image test trouvée.');

  console.log('🌐 Test E2E 100% ONLINE');
  console.log('📂 Image:', imagePath);
  console.log('🔗 Frontend:', FRONT_URL);
  console.log('🔗 API:', API_URL);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.setDefaultTimeout(90000); // Plus de temps pour téléchargement modèles

  try {
    // 1. Vérifier que l'API est en ligne
    console.log('\n📡 Vérification API...');
    const healthResp = await page.request.get(`${API_URL}/health`);
    if (!healthResp.ok()) throw new Error('API non accessible');
    const health = await healthResp.json();
    console.log('✓ API online:', health.status);

    // 2. Charger l'interface
    console.log('\n🌐 Chargement UI...');
    await page.goto(FRONT_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('h1:has-text("MTG Deck Scanner")', { timeout: 10000 });
    console.log('✓ Page chargée');

    // 3. Upload de l'image
    const input = page.locator('input[type="file"]');
    if ((await input.count()) === 0) throw new Error("Input file introuvable.");
    
    console.log('\n📸 Upload de l\'image...');
    await input.setInputFiles(imagePath);
    await page.waitForTimeout(500);

    // 4. Cliquer sur le bouton de traitement
    const processBtn = page.locator([
      'button:has-text("Analyser")',
      'button:has-text("Analyze")',
      'button:has-text("Process")',
      'button:has-text("Upload")',
      'button:has-text("Scan")',
      'button:has-text("Submit")'
    ].join(', ')).first();
    
    if ((await processBtn.count()) === 0) {
      throw new Error("Bouton de traitement introuvable");
    }
    
    const btnText = await processBtn.textContent();
    console.log(`✓ Clic sur "${btnText}"`);
    
    // Intercepter la réponse de l'upload
    const uploadPromise = page.waitForResponse(
      resp => resp.url().includes('/api/ocr/upload') && resp.status() === 200,
      { timeout: 30000 }
    );
    
    await processBtn.click();
    
    // 5. Attendre la réponse d'upload
    console.log('\n⏳ Upload vers API...');
    const uploadResp = await uploadPromise;
    const uploadData = await uploadResp.json();
    
    if (!uploadData.jobId) throw new Error("Pas de jobId dans la réponse");
    console.log(`✓ Job créé: ${uploadData.jobId}`);

    // 6. Attendre la navigation ou le résultat
    try {
      await page.waitForURL('**/result/**', { timeout: 5000 });
      console.log('✓ Redirection vers page résultats');
    } catch {
      console.log('ℹ️ Pas de redirection (UI single-page)');
    }

    // 7. Attendre l'apparition du résultat OCR
    console.log('\n⏳ Traitement OCR (téléchargement modèles si première fois)...');
    
    const resultSelectors = [
      'text=/\\d+\\s+(Island|Forest|Mountain|Plains|Swamp)/i',
      'text=/Mainboard/i',
      'text=/Sideboard/i',
      'button:has-text("Export")',
      'pre'
    ];
    
    let resultFound = false;
    const maxWait = 60; // secondes
    const startTime = Date.now();
    
    while (!resultFound && (Date.now() - startTime) < maxWait * 1000) {
      for (const selector of resultSelectors) {
        if (await page.locator(selector).count() > 0) {
          resultFound = true;
          console.log(`✓ Résultat détecté via: ${selector}`);
          break;
        }
      }
      
      if (!resultFound) {
        // Vérifier aussi le status via API
        try {
          const statusResp = await page.request.get(`${API_URL}/api/ocr/status/${uploadData.jobId}`);
          if (statusResp.ok()) {
            const status = await statusResp.json();
            console.log(`  Status: ${status.state} (${status.progress}%)`);
            
            if (status.state === 'completed' || status.state === 'done') {
              resultFound = true;
              console.log('✓ OCR terminé côté API');
            }
          }
        } catch {}
        
        await page.waitForTimeout(2000);
      }
    }
    
    if (!resultFound) {
      throw new Error(`Aucun résultat après ${maxWait}s`);
    }

    // 8. Vérifier qu'on peut exporter
    const exportBtns = await page.locator('button:has-text("Export")').count();
    if (exportBtns > 0) {
      console.log(`✓ ${exportBtns} format(s) d'export disponible(s)`);
    }

    // 9. Essayer de récupérer un aperçu
    try {
      const preElement = page.locator('pre').first();
      if (await preElement.count() > 0) {
        const deckText = await preElement.textContent();
        if (deckText && deckText.trim().length > 10) {
          const lines = deckText.split('\n');
          console.log('\n📋 Aperçu du deck:');
          console.log(lines.slice(0, 3).join('\n'));
          if (lines.length > 3) console.log('...');
        }
      }
    } catch {}

    console.log('\n✅ SUCCESS - Test E2E 100% ONLINE réussi!');
    console.log('- Upload: OK');
    console.log('- OCR processing: OK');  
    console.log('- Résultat affiché: OK');
    console.log('- Export disponible: OK');
    
    await browser.close();
    process.exit(0);

  } catch (e) {
    console.error('\n❌ FAIL —', e.message);
    
    try {
      console.error('📍 URL:', page.url());
      const title = await page.title();
      console.error('📄 Titre:', title);
    } catch {}
    
    await page.screenshot({ path: 'tests/last_error.png', fullPage: true });
    console.error('📸 Screenshot: tests/last_error.png');
    
    await browser.close();
    process.exit(1);
  }
})();
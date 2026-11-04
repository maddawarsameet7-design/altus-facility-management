import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const distClient = path.resolve(__dirname, '..', 'dist', 'client');

// Simple static file server for dist/client
function createServer(port) {
  const mimeTypes = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.xml': 'application/xml',
    '.txt': 'text/plain',
  };

  const server = http.createServer((req, res) => {
    let reqPath = req.url.split('?')[0];
    if (reqPath.endsWith('/')) {
      reqPath += 'index.html';
    }

    let filePath = path.join(distClient, reqPath);
    if (!fs.existsSync(filePath) && fs.existsSync(filePath + '.html')) {
      filePath = filePath + '.html';
    } else if (fs.existsSync(path.join(filePath, 'index.html'))) {
      filePath = path.join(filePath, 'index.html');
    }

    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const ext = path.extname(filePath).toLowerCase();
      const contentType = mimeTypes[ext] || 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': contentType });
      fs.createReadStream(filePath).pipe(res);
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('404 Not Found');
    }
  });

  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => {
      resolve(server);
    });
  });
}

async function runAudit() {
  const PORT = 4321;
  const server = await createServer(PORT);
  console.log(`Local test server serving dist/client at http://127.0.0.1:${PORT}`);

  let chrome;
  try {
    chrome = await chromeLauncher.launch({
      chromeFlags: ['--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    });

    const targetUrl = `http://127.0.0.1:${PORT}/`;
    console.log(`Running Lighthouse Mobile audit on ${targetUrl} (Chrome port: ${chrome.port})...`);

    const runnerResult = await lighthouse(
      targetUrl,
      {
        logLevel: 'error',
        output: 'json',
        onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
        port: chrome.port,
      },
      {
        extends: 'lighthouse:default',
        settings: {
          formFactor: 'mobile',
          screenEmulation: {
            mobile: true,
            width: 412,
            height: 823,
            deviceScaleFactor: 2.625,
            disabled: false,
          },
          throttling: {
            rttMs: 150,
            throughputKbps: 1638.4,
            requestLatencyMs: 562.5,
            downloadThroughputKbps: 1474.56,
            uploadThroughputKbps: 675,
            cpuSlowdownMultiplier: 4,
          },
        },
      }
    );

    const report = runnerResult.lhr;
    const categories = report.categories;

    const scores = {
      performance: Math.round((categories.performance?.score || 0) * 100),
      accessibility: Math.round((categories.accessibility?.score || 0) * 100),
      bestPractices: Math.round((categories['best-practices']?.score || 0) * 100),
      seo: Math.round((categories.seo?.score || 0) * 100),
    };

    console.log('\n====================================================');
    console.log('📱 LIGHTHOUSE MOBILE AUDIT REPORT — ALTSAN.COM (HOME)');
    console.log('====================================================');
    console.log(`Target URL:      ${targetUrl}`);
    console.log(`Device / Mode:   Mobile (Simulated Moto G4 / Slow 4G)`);
    console.log(`Lighthouse Ver:  ${report.lighthouseVersion}`);
    console.log(`----------------------------------------------------`);
    console.log(`⚡ Performance:    ${scores.performance} / 100  ${scores.performance >= 90 ? '✅ PASSED' : '❌ FAILED'}`);
    console.log(`♿ Accessibility:  ${scores.accessibility} / 100  ${scores.accessibility >= 90 ? '✅ PASSED' : '❌ FAILED'}`);
    console.log(`🛡️  Best Practices: ${scores.bestPractices} / 100  ${scores.bestPractices >= 90 ? '✅ PASSED' : '❌ FAILED'}`);
    console.log(`🔍 SEO:            ${scores.seo} / 100  ${scores.seo >= 90 ? '✅ PASSED' : '❌ FAILED'}`);
    console.log('====================================================\n');

    const reportSummary = {
      timestamp: new Date().toISOString(),
      url: targetUrl,
      scores,
      audits: {
        fcp: report.audits['first-contentful-paint']?.displayValue,
        lcp: report.audits['largest-contentful-paint']?.displayValue,
        tbt: report.audits['total-blocking-time']?.displayValue,
        cls: report.audits['cumulative-layout-shift']?.displayValue,
        speedIndex: report.audits['speed-index']?.displayValue,
      },
    };

    fs.writeFileSync(
      path.join(__dirname, '..', 'lighthouse-report.json'),
      JSON.stringify(reportSummary, null, 2)
    );
    console.log('Saved detailed audit metrics to lighthouse-report.json');

    const allPassed = Object.values(scores).every((s) => s >= 90);
    if (!allPassed) {
      console.warn('⚠️ One or more categories did not meet the > 90 threshold.');
    }
  } catch (err) {
    console.error('Lighthouse execution error:', err);
  } finally {
    if (chrome) await chrome.kill();
    server.close();
  }
}

runAudit();


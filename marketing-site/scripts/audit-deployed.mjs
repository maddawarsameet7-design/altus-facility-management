import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
import fs from 'node:fs';

async function audit() {
  const targetUrl = 'https://marketing-site-sepia-pi.vercel.app/';
  const bypassToken = 'cRWg0ZjT9rmRX5dFfAqYuDcOjRMWP9A0';

  console.log(`Auditing deployed Vercel URL: ${targetUrl}`);

  const chrome = await chromeLauncher.launch({
    chromeFlags: ['--headless', '--no-sandbox', '--disable-gpu'],
  });

  try {
    const runnerResult = await lighthouse(
      targetUrl,
      {
        logLevel: 'error',
        output: 'json',
        onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
        port: chrome.port,
        extraHeaders: {
          'x-vercel-protection-bypass': bypassToken,
        },
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
    console.log('📱 LIGHTHOUSE MOBILE AUDIT REPORT — LIVE VERCEL DEPLOYMENT');
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

    fs.writeFileSync(
      'deployed-report.json',
      JSON.stringify(
        {
          url: targetUrl,
          scores,
          audits: {
            fcp: report.audits['first-contentful-paint']?.displayValue,
            lcp: report.audits['largest-contentful-paint']?.displayValue,
            tbt: report.audits['total-blocking-time']?.displayValue,
            cls: report.audits['cumulative-layout-shift']?.displayValue,
            speedIndex: report.audits['speed-index']?.displayValue,
          },
        },
        null,
        2
      )
    );
  } finally {
    await chrome.kill();
  }
}

audit();


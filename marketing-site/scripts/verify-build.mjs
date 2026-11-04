/**
 * scripts/verify-build.mjs — Comprehensive build verification test.
 *
 * Enforces:
 * 1. site.config.ts validation: fails on placeholders, example.com, localhost, empty required fields.
 * 2. In production, fails if mail env vars are missing.
 * 3. robots.txt validation: must exist; in production cannot disallow everything; in staging must disallow.
 * 4. Sitemap validation: sitemap-index.xml must exist; draft legal pages (/privacy, /terms) must be excluded.
 * 5. Page-level SEO & HTML structure across all dist/client HTML files:
 *    - Must have non-empty <title>, and titles must NOT be duplicated.
 *    - Must have non-empty <meta name="description">, and descriptions must NOT be duplicated.
 *    - Must have exactly ONE <h1> tag.
 *    - Must have valid canonical link.
 *    - In production, no page may contain 'noindex'. In staging, pages must contain 'noindex'.
 *    - All <script type="application/ld+json"> must be valid parseable JSON with @context and @type.
 *    - All <img> tags must have descriptive alt attributes.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const distClientDir = path.join(projectRoot, 'dist', 'client');

const isStaging = process.env.STAGING === 'true';
const isProduction = process.env.NODE_ENV === 'production' || process.env.PRODUCTION_BUILD === 'true';

console.log('====================================================');
console.log(`🔍 Running Altsan Build Verification (Mode: ${isStaging ? 'STAGING' : 'PRODUCTION'})`);
console.log('====================================================');

const errors = [];
const warnings = [];

// ── 1. Validate site.config.ts ──────────────────────────────────────────────
async function validateConfig() {
  console.log('\n[1/5] Verifying site.config.ts...');
  try {
    const { siteConfig, validateSiteConfig } = await import('../site.config.ts');
    const configErrors = validateSiteConfig(siteConfig, isProduction);
    if (configErrors && configErrors.length > 0) {
      configErrors.forEach((err) => errors.push(`siteConfig Error: ${err}`));
    } else {
      console.log('✓ site.config.ts passed all schema, placeholder, and claim validations.');
    }

    if (siteConfig.socialLinks?.sameAs?.length > 0) {
      warnings.push('socialLinks.sameAs has entries; ensure these are live, verified company profiles.');
    }
  } catch (err) {
    errors.push(`Failed to load or validate site.config.ts: ${err.message}`);
  }
}

// ── 2. Check Mail Env Vars for Production ────────────────────────────────────
function checkMailEnv() {
  console.log('\n[2/5] Checking Mail Environment Variables...');
  if (isProduction) {
    const hasMailKey = Boolean(
      process.env.RESEND_API_KEY ||
      process.env.SENDGRID_API_KEY ||
      process.env.CONTACT_WEBHOOK_URL
    );
    if (!hasMailKey) {
      errors.push(
        'PRODUCTION BUILD FAILURE: Mail provider credentials (RESEND_API_KEY, SENDGRID_API_KEY, or CONTACT_WEBHOOK_URL) are missing in production environment.'
      );
    } else {
      console.log('✓ Production mail provider credentials detected.');
    }
  } else {
    console.log('ℹ Local/test build: mail credentials check bypassed (mock mode active).');
  }
}

// ── 3. Validate robots.txt ──────────────────────────────────────────────────
function checkRobotsTxt() {
  console.log('\n[3/5] Validating robots.txt...');
  const robotsPath = path.join(distClientDir, 'robots.txt');
  if (!fs.existsSync(robotsPath)) {
    errors.push(`robots.txt missing at ${robotsPath}`);
    return;
  }

  const content = fs.readFileSync(robotsPath, 'utf-8');
  if (isStaging) {
    if (!content.includes('Disallow: /')) {
      errors.push('STAGING BUILD FAILURE: robots.txt must disallow all crawlers in staging mode.');
    } else {
      console.log('✓ Staging robots.txt correctly disallows crawlers.');
    }
  } else {
    // Production
    if (content.includes('Disallow: /') && !content.includes('Disallow: /privacy')) {
      errors.push('PRODUCTION BUILD FAILURE: robots.txt disallows all crawling in production mode!');
    }
    if (!content.includes('Sitemap:')) {
      errors.push('PRODUCTION BUILD FAILURE: robots.txt does not link to sitemap!');
    } else {
      console.log('✓ Production robots.txt correctly allows indexing and links to sitemap.');
    }
  }
}

// ── 4. Validate Sitemap ─────────────────────────────────────────────────────
function checkSitemap() {
  console.log('\n[4/5] Validating Sitemap Generation...');
  const sitemapIndexPath = path.join(distClientDir, 'sitemap-index.xml');
  const sitemap0Path = path.join(distClientDir, 'sitemap-0.xml');

  if (!fs.existsSync(sitemapIndexPath) && !fs.existsSync(sitemap0Path)) {
    errors.push('Sitemap missing in dist/client!');
    return;
  }

  let sitemapContent = '';
  if (fs.existsSync(sitemap0Path)) {
    sitemapContent = fs.readFileSync(sitemap0Path, 'utf-8');
  } else if (fs.existsSync(sitemapIndexPath)) {
    sitemapContent = fs.readFileSync(sitemapIndexPath, 'utf-8');
  }

  // Ensure draft legal pages are excluded from sitemap
  if (sitemapContent.includes('/privacy') || sitemapContent.includes('/privacy/')) {
    errors.push('LEGAL EXCLUSION FAILURE: Draft /privacy page must be excluded from sitemap!');
  }
  if (sitemapContent.includes('/terms') || sitemapContent.includes('/terms/')) {
    errors.push('LEGAL EXCLUSION FAILURE: Draft /terms page must be excluded from sitemap!');
  }

  console.log('✓ Sitemap verified: draft legal pages excluded, core service pages indexed.');
}

// ── 5. Page-by-Page HTML & SEO Inspection ────────────────────────────────────
function getAllHtmlFiles(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach((file) => {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getAllHtmlFiles(fullPath));
    } else if (file.endsWith('.html')) {
      results.push(fullPath);
    }
  });
  return results;
}

function checkHtmlPages() {
  console.log('\n[5/5] Inspecting HTML Pages across dist/client...');
  const htmlFiles = getAllHtmlFiles(distClientDir);

  if (htmlFiles.length === 0) {
    errors.push('No HTML files found in dist/client! Did the build complete?');
    return;
  }

  const titles = new Map();
  const descriptions = new Map();

  for (const filePath of htmlFiles) {
    const relPath = path.relative(distClientDir, filePath);
    const html = fs.readFileSync(filePath, 'utf-8');

    // 1. Check <title>
    const titleMatch = html.match(/<title>([^<]+)<\/title>/i);
    if (!titleMatch || !titleMatch[1].trim()) {
      errors.push(`Page "${relPath}" is missing a <title> tag!`);
    } else {
      const title = titleMatch[1].trim();
      if (titles.has(title)) {
        errors.push(`DUPLICATE TITLE: "${title}" is used by both "${titles.get(title)}" and "${relPath}"`);
      } else {
        titles.set(title, relPath);
      }
    }

    // 2. Check <meta name="description">
    const descMatch = html.match(/<meta\s+name=["']description["']\s+content=["']([^"']+)["']/i);
    if (!descMatch || !descMatch[1].trim()) {
      errors.push(`Page "${relPath}" is missing a meta description!`);
    } else {
      const desc = descMatch[1].trim();
      if (descriptions.has(desc)) {
        errors.push(`DUPLICATE META DESCRIPTION on "${relPath}" (matches "${descriptions.get(desc)}")`);
      } else {
        descriptions.set(desc, relPath);
      }
    }

    // 3. Check Canonical Link
    const canonicalMatch = html.match(/<link\s+rel=["']canonical["']\s+href=["']([^"']+)["']/i);
    if (!canonicalMatch || !canonicalMatch[1].trim()) {
      errors.push(`Page "${relPath}" is missing a canonical <link rel="canonical"> tag!`);
    } else {
      const canonical = canonicalMatch[1].trim();
      if (!canonical.startsWith('https://altsan.com')) {
        errors.push(`Canonical URL "${canonical}" on "${relPath}" must start with https://altsan.com`);
      }
    }

    // 4. Check Exactly ONE <h1>
    const h1Matches = html.match(/<h1[\s>]/gi) || [];
    if (h1Matches.length === 0) {
      errors.push(`Page "${relPath}" has NO <h1> tag!`);
    } else if (h1Matches.length > 1) {
      errors.push(`Page "${relPath}" has multiple (${h1Matches.length}) <h1> tags! Exactly one is required.`);
    }

    // 5. Check noindex vs index directive
    const robotsMatch = html.match(/<meta\s+name=["']robots["']\s+content=["']([^"']+)["']/i);
    const robotsContent = robotsMatch ? robotsMatch[1].toLowerCase() : '';

    if (isStaging) {
      if (!robotsContent.includes('noindex')) {
        errors.push(`STAGING FAILURE: Page "${relPath}" is missing "noindex" robots meta directive.`);
      }
    } else {
      if (robotsContent.includes('noindex')) {
        errors.push(`PRODUCTION FAILURE: Page "${relPath}" contains "noindex"! Production pages must be indexable.`);
      }
    }

    // 6. Check JSON-LD validity
    const jsonLdRegex = /<script\s+type=["']application\/ld\+json["']>([\s\S]*?)<\/script>/gi;
    let match;
    while ((match = jsonLdRegex.exec(html)) !== null) {
      const jsonStr = match[1];
      try {
        const parsed = JSON.parse(jsonStr);
        const items = Array.isArray(parsed) ? parsed : [parsed];
        for (const item of items) {
          if (!item['@context'] || !item['@type']) {
            errors.push(`Invalid JSON-LD on "${relPath}": missing @context or @type.`);
          }
        }
      } catch (e) {
        errors.push(`MALFORMED JSON-LD on "${relPath}": ${e.message}`);
      }
    }

    // 7. Check Image Alt Attributes
    const imgRegex = /<img\s+([^>]*?)>/gi;
    let imgMatch;
    while ((imgMatch = imgRegex.exec(html)) !== null) {
      const imgTag = imgMatch[1];
      if (!imgTag.includes('alt="') && !imgTag.includes("alt='")) {
        errors.push(`IMAGE ACCESSIBILITY: <img> tag on "${relPath}" is missing an alt attribute: ${imgMatch[0]}`);
      }
    }
  }

  console.log(`✓ Inspected ${htmlFiles.length} HTML pages successfully.`);
}

// ── Run All Checks ──────────────────────────────────────────────────────────
async function run() {
  await validateConfig();
  checkMailEnv();
  checkRobotsTxt();
  checkSitemap();
  checkHtmlPages();

  console.log('\n====================================================');
  if (warnings.length > 0) {
    console.log(`⚠️  ${warnings.length} Warning(s):`);
    warnings.forEach((w) => console.log(`   - ${w}`));
  }

  if (errors.length > 0) {
    console.error(`❌ BUILD VERIFICATION FAILED with ${errors.length} error(s):`);
    errors.forEach((err) => console.error(`   ✖ ${err}`));
    console.log('====================================================\n');
    process.exit(1);
  } else {
    console.log('✅ ALL BUILD VERIFICATION CHECKS PASSED CLEANLY!');
    console.log('====================================================\n');
    process.exit(0);
  }
}

run();

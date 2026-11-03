import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const distDir = path.resolve(__dirname, '../dist');

if (!fs.existsSync(distDir)) {
  console.error('❌ dist/ directory does not exist. Run npm run build first.');
  process.exit(1);
}

const FORBIDDEN_STRINGS = [
  'password123',
  'Quick login',
  'Quick Select',
  '1-Tap Demo Quick Select',
  '1-Tap Demo',
  '👑 Director',
  '🏢 Chairman',
  '👷 Supervisor',
  '🏠 Member',
  '⚡ Worker',
];
let foundIssues = 0;

function scanDir(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      scanDir(fullPath);
    } else if (entry.isFile()) {
      const content = fs.readFileSync(fullPath, 'utf8');
      for (const forbidden of FORBIDDEN_STRINGS) {
        if (content.toLowerCase().includes(forbidden.toLowerCase())) {
          console.error(`❌ Security Violation: Found forbidden string "${forbidden}" in ${path.relative(distDir, fullPath)}`);
          foundIssues++;
        }
      }
    }
  }
}

scanDir(distDir);

if (foundIssues === 0) {
  console.log('✅ Production build security check PASSED: No dev credentials or quick-login buttons present in dist/.');
  process.exit(0);
} else {
  console.error(`❌ Production build security check FAILED: ${foundIssues} forbidden occurrences found.`);
  process.exit(1);
}

import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import vercel from '@astrojs/vercel';

// https://astro.build/config
export default defineConfig({
  site: 'https://altsan.com',
  output: 'static',
  adapter: vercel({
    webAnalytics: { enabled: false },
    speedInsights: { enabled: false }
  }),
  integrations: [
    sitemap({
      filter: (page) => {
        // Exclude draft legal pages until lawyer review confirmed
        const url = page.toLowerCase();
        return !url.includes('/privacy') && !url.includes('/terms');
      }
    })
  ]
});


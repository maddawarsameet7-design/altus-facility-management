import type { APIRoute } from 'astro';
import { siteConfig } from '../config/site';

export const GET: APIRoute = () => {
  const isStaging = import.meta.env.STAGING === 'true' || process.env.STAGING === 'true';

  let robotsContent = '';
  if (isStaging) {
    robotsContent = `User-agent: *
Disallow: /
`;
  } else {
    robotsContent = `User-agent: *
Allow: /

Sitemap: ${siteConfig.url}/sitemap-index.xml
`;
  }

  return new Response(robotsContent, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
    },
  });
};


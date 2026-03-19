

import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://o3djeeps.com',
  integrations: [sitemap()],
});
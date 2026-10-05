// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import sitemap from '@astrojs/sitemap';

// GitHub Pages project site. To move to a custom domain (e.g.
// benchmark.opennav.org) set `site` to it and drop `base`.
export default defineConfig({
  site: 'https://open-navigation.github.io',
  base: '/opennav_robotics_workload_benchmark',
  trailingSlash: 'ignore',
  integrations: [
    starlight({
      title: 'Robotics Workload Benchmark',
      description:
        'An independently managed, vendor-agnostic robotics and AI workload ' +
        'benchmark from Open Navigation.',
      disable404Route: true,
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/open-navigation/opennav_robotics_workload_benchmark',
        },
      ],
      customCss: ['./src/styles/tokens.css', './src/styles/starlight.css'],
      sidebar: [
        { label: 'Overview', link: '/docs/' },
        { label: 'Run the benchmark', link: '/docs/reproduce/' },
        {
          label: 'Platform setup',
          items: [
            { label: 'AMD Strix Halo', link: '/docs/platform-setup/amd-strix-halo/' },
            { label: 'Jetson Orin', link: '/docs/platform-setup/jetson-orin/' },
            { label: 'Jetson Thor', link: '/docs/platform-setup/jetson-thor/' },
          ],
        },
        { label: 'Adding a platform', link: '/docs/adding-a-platform/' },
      ],
      components: {
        SiteTitle: './src/components/DocsSiteTitle.astro',
      },
    }),
    sitemap(),
  ],
});

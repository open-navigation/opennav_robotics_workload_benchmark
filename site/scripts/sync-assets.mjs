/**
 * Copy assets that live in the repo (and are the canonical copies there) into
 * the site's public/ directory, so they are served at stable URLs without
 * being duplicated in version control.
 */
import { copyFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const siteDir = dirname(dirname(fileURLToPath(import.meta.url)));
const repoDir = dirname(siteDir);

const assets = [
  ['docs/Robotics Workload Platform Benchmarking Results.pdf',
    'public/Robotics-Workload-Platform-Benchmarking-Results.pdf'],
  ['docs/images/benchmark_run.gif', 'public/images/benchmark_run.gif'],
  ['docs/images/benchmark_demo.gif', 'public/images/benchmark_demo.gif'],
  ['docs/images/gazebo.png', 'public/images/gazebo.png'],
  ['docs/images/rviz2.png', 'public/images/rviz2.png'],
  ['docs/images/opennav-mark.png', 'public/images/opennav-mark.png'],
];

// A missing source is a hard failure: public/images/ is gitignored, so a
// silent skip here ships a build with a broken image and nothing to show for
// it until someone loads the page.
const failures = [];

for (const [from, to] of assets) {
  const dest = join(siteDir, to);
  await mkdir(dirname(dest), { recursive: true });
  try {
    await copyFile(join(repoDir, from), dest);
    console.log(`synced ${to}`);
  } catch (err) {
    failures.push(`${from}: ${err.message}`);
  }
}

if (failures.length > 0) {
  console.error('could not sync required assets:');
  for (const failure of failures) console.error(`  ${failure}`);
  process.exit(1);
}

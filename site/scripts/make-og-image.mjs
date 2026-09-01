/**
 * Regenerate public/og.png, the social card.
 *
 * Numbers come from the exported dataset, so the card cannot drift from the
 * results. Run after `export_site_data.py` changes the headline figures:
 *
 *     node scripts/make-og-image.mjs
 *
 * Requires a local Chrome/Chromium. The output is committed, so CI never
 * needs a browser.
 */
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const siteDir = dirname(dirname(fileURLToPath(import.meta.url)));
const runs = Object.fromEntries(
  JSON.parse(readFileSync(join(siteDir, 'src/data/runs.json'), 'utf8')).map((r) => [r.id, r]),
);
const mark = readFileSync(join(siteDir, 'public/images/opennav-mark.png')).toString('base64');

const CARDS = [
  ['max_power__amd_strix_halo', 'Strix Halo', '#eb6834'],
  ['max_power__jetson_thor', 'Jetson Thor', '#1baf7a'],
  ['max_power__jetson_orin', 'Jetson AGX Orin', '#4a3aa7'],
];

const cards = CARDS.map(([id, name, color]) => {
  const r = runs[id];
  return `<div class="card" style="--c:${color}">
    <div class="bar"></div>
    <div class="name">${name}</div>
    <div class="row"><span>CPU free</span><b>${r.derived.cpu_available_percent.toFixed(1)}%</b></div>
    <div class="row"><span>Missions</span><b>${r.application.completed_missions}</b></div>
    <div class="row"><span>Misses/s</span><b>${r.application.control_loop_misses_per_sec.toFixed(2)}</b></div>
  </div>`;
}).join('');

const html = `<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@500&display=swap">
<style>
*{box-sizing:border-box;margin:0}
body{width:1200px;height:630px;background:#111214;color:#f2f2f2;font-family:Inter,sans-serif;
  padding:64px 72px;display:flex;flex-direction:column;justify-content:space-between;
  background-image:radial-gradient(700px 340px at 88% -8%, rgba(0,173,238,.18), transparent 70%)}
.top{display:flex;align-items:center;gap:16px}
.top img{width:44px;height:44px}
.brand{font-family:Poppins,sans-serif;font-weight:600;font-size:19px;letter-spacing:.02em}
.brand span{color:#47c6ee}
h1{font-family:Poppins,sans-serif;font-size:62px;line-height:1.06;letter-spacing:-.02em;max-width:15ch}
.sub{font-size:21px;color:#c2c5c8;max-width:60ch;margin-top:18px}
.cards{display:flex;gap:18px}
.card{flex:1;background:#1a1a1c;border:1px solid #2e3033;border-radius:12px;padding:20px 22px;position:relative;overflow:hidden}
.bar{position:absolute;inset:0 0 auto 0;height:4px;background:var(--c)}
.name{font-family:Poppins,sans-serif;font-weight:600;font-size:19px;margin:8px 0 12px}
.row{display:flex;justify-content:space-between;align-items:baseline;padding:4px 0;font-size:14px;color:#9a9ea2}
.row b{font-family:'JetBrains Mono',monospace;font-size:19px;color:#f2f2f2;font-weight:500}
.foot{font-size:15px;color:#9a9ea2;display:flex;justify-content:space-between;align-items:center}
</style></head><body>
<div>
  <div class="top"><img src="data:image/png;base64,${mark}"><div class="brand">Open Navigation <span>· Robotics Workload Benchmark</span></div></div>
  <h1 style="margin-top:34px">The whole robot benchmark, fully loaded.</h1>
  <div class="sub">An independently managed, vendor-agnostic benchmark: a full Nav2 autonomy stack and an edge AI workload, running at the same time, on the same computer.</div>
</div>
<div class="cards">${cards}</div>
<div class="foot"><span>Max power · 900 s · 3 platforms</span><span>opennav.org</span></div>
</body></html>`;

const dir = mkdtempSync(join(tmpdir(), 'og-'));
const page = join(dir, 'og.html');
writeFileSync(page, html);

const chrome =
  process.env.CHROME_BIN ?? ['google-chrome', 'chromium', 'chromium-browser'].find(Boolean);

execFileSync(chrome, [
  '--headless',
  '--disable-gpu',
  '--no-sandbox',
  '--hide-scrollbars',
  '--window-size=1200,630',
  '--virtual-time-budget=8000',
  `--screenshot=${join(siteDir, 'public/og.png')}`,
  `file://${page}`,
]);

console.log('wrote public/og.png');

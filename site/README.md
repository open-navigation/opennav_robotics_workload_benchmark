# The benchmark website

The source for the published benchmark results site. It is an [Astro](https://astro.build) project
using [Starlight](https://starlight.astro.build) for the documentation section, built and deployed to
GitHub Pages by [`.github/workflows/site.yml`](../.github/workflows/site.yml).

There is no `gh-pages` branch. The workflow uploads a build artifact and deploys it through
`actions/deploy-pages`, so the repository's Pages source is set to **GitHub Actions**, not a branch.
Everything the site needs lives on `main`.

## Where the data comes from

This is the one thing to understand before changing anything:

```
opennav_benchmark_logs/           the raw runs, one directory per platform per category
  └─ export_site_data.py          reads them, computes stats and derived metrics
       ├─ site/src/data/          imported by Astro at build time
       └─ site/public/data/       served as-is: dataset.json and the per-run CSVs
```

**Both output directories are committed to the repo, and the site build never runs the exporter.**
The build consumes whatever is committed. That keeps the published dataset reviewable in pull request
diffs and keeps Python out of the deploy path — at the cost of one rule you have to follow, described
under [The contract](#the-contract) below.

The exporter is the only place a benchmark category is named. Routes are generated from the data —
`getStaticPaths()` in `src/pages/results/[category].astro` maps over the exported categories and
`src/pages/platforms/[platform].astro` maps over `platformOrder` — so **adding a category is an
exporter change alone**. Adding a *platform* is not: it also needs a color, prose, and a docs page
that cannot be inferred from measurements. See [Adding a platform](#adding-a-platform) below.

## Prerequisites

- **Node 22** — for building the site.
- **Python 3.12** with `pip install -r opennav_benchmark_analysis/requirements.txt` — only needed to
  re-export the data. If you are just editing pages or styles, you can skip it.

## Commands

Run these **from the repository root**, not from `site/`. The Makefile targets and the exporter's
default `--logs-dir` / `--site-dir` are both resolved relative to the root.

| Command | Does |
| --- | --- |
| `make site-data` | Re-export the dataset from `opennav_benchmark_logs/` |
| `make site-check` | What CI's `data` job runs: registry check, then verify the committed dataset is current |
| `make site` | Export, then build into `site/dist/` |
| `make site-dev` | Local dev server with hot reload |

`make site-dev` deliberately does not re-export. The committed dataset is enough for a fresh clone to
run the site immediately.

## The contract

After changing anything under `opennav_benchmark_logs/`, or `export_site_data.py`, or
`opennav_benchmark_analysis/utils.py`, run:

```sh
make site-data
git add site/src/data site/public/data
```

and include those files **in the same commit**. CI re-exports and compares, so a dataset that has
drifted from the logs fails the build:

```
The committed site dataset does not match a fresh export of opennav_benchmark_logs/.
```

Run `make site-check` before pushing to catch it locally. Because `deploy` is gated behind the data
checks with `needs:`, a failure here means nothing is published — the previously deployed site stays
up.

## Adding a run to an existing platform

Drop the run into `opennav_benchmark_logs/<category>/<name>/` and add a `RunSpec` to the matching
`Category` in `CATEGORIES` (`export_site_data.py`). A `RunSpec` is
`(key, platform, label, log_dir, tdp_w=..., note='')`, where `key` is unique within the category,
`platform` is a key from `PLATFORMS`, and `log_dir` is relative to the logs root. Then
`make site-data` and commit. Nothing in the website enumerates runs.

The exporter only looks at directories declared in `CATEGORIES`. One that exists on disk but is not
declared is **not** silently ignored — `--strict` fails and names it, because a run needs a display
label, a TDP, and a publish decision that cannot be inferred. `--strict` checks both directions, so
it also fails when a published `RunSpec` points at a log directory that no longer exists; otherwise a
rename would quietly drop a platform from the comparison.

Two `RunSpec`s may point at the same `log_dir` — `balanced_power`'s Orin entry reuses
`max_power/jetson_orin`, since that board is already at its maximum TDP. Use `note=` to explain any
such reuse; it renders on the results page.

## Adding a category

Add a `Category` to `CATEGORIES` with a unique `key`, a `label`, an `order` (controls display
order), a `description`, and its `runs`. Set `published=False` to keep it out of the site while
still registering its log directories; flip it to `True` and re-export to publish. Routes, selectors,
tables and charts all follow from the data — no site edits.

## Adding a platform

This is the one change that spans both sides of the repo. A new board needs a color, prose, and
documentation that no measurement can supply. Work through all of it, then `make site-data`.

**In `opennav_benchmark_analysis/`:**

1. `utils.py` → `PLATFORM_LABELS`: the canonical key and display name.
2. `export_site_data.py` → `SENSOR_DRIVER_LOAD`: measured per-sensor CPU cost, as a fraction of one
   core. Mirrors `HARDWARE_PROFILES` in
   `opennav_benchmark_pipeline/scripts/hardware_platforms.py`; keep the two in step.
3. `export_site_data.py` → `PLATFORMS`: the full record — `slug` (its URL and docs filename),
   `label` / `short_label` / `tile_label`, `vendor`, `vendor_url`, `summary`, the `spec` block, and
   `as_tested`. Copy an existing entry and fill every field; pages render them positionally.
4. `export_site_data.py` → `PLATFORM_ORDER`: controls column and series order site-wide.
5. `export_site_data.py` → `CATEGORIES`: a `RunSpec` in each category it competes in.

**In `site/`:**

6. `src/styles/tokens.css` → a `--series-<name>` variable in **all three** theme blocks: bare
   `:root`, the `prefers-color-scheme: dark` block, and the `[data-theme="dark"]` block. Missing the
   dark ones gives a color that vanishes for half your readers. The palette is a validated
   categorical set — pick a hue that stays distinguishable from the existing three in both themes.
7. `src/lib/data.ts` → `seriesVar`: map the platform key to that variable. This is the single source
   of truth; `lib/charts.ts` and every page read it through `colorFor()`. **It fails soft** — an
   unmapped platform renders in neutral grey rather than erroring, so open a chart and a results
   table and confirm the new color actually appears.
8. `src/content/platform-notes.ts` → `PLATFORM_NOTES`: `verdict`, `strengths`, `limits`. Read the
   header comment first — nothing here may assert anything the report does not.
9. `src/pages/platforms/[platform].astro` → the `setupDoc` map, linking the platform key to the
   filename of its setup page.
10. `src/content/docs/docs/platform-setup/<slug>.md` → a new Starlight page with `title` and
    `description` frontmatter.
11. `astro.config.mjs` → a sidebar entry under "Platform setup". The sidebar is hand-maintained; a
    page absent from it builds and is reachable by URL but appears in no navigation.
12. `scripts/make-og-image.mjs` → the `CARDS` array, if the board should appear on the social card.
    Re-run it (see [The social card](#the-social-card)).

Finally, `make site-check` and `make site-dev`, then check the home page, `/platforms/<slug>`, and
one `/results/<category>` page.

See [Adding a platform](src/content/docs/docs/adding-a-platform.md) for the contributor-facing
submission process.

## Editing the site itself

| To change | Edit |
| --- | --- |
| Home page, headline findings | `src/pages/index.astro` |
| Methodology / About prose | `src/pages/methodology.astro`, `src/pages/about.astro` |
| Per-category comparison page | `src/pages/results/[category].astro` |
| Per-platform page | `src/pages/platforms/[platform].astro` |
| **Which charts exist, and their tables** | `src/lib/charts.ts` |
| Chart rendering and interaction | `src/components/Chart.astro`, `src/scripts/charts.ts` |
| Colors, spacing, typography | `src/styles/tokens.css` |
| Header, footer, meta tags | `src/layouts/BaseLayout.astro` |

`src/lib/charts.ts` is where nearly all chart work happens. `comparisonSections()` builds the
multi-platform charts for a category page and `singleRunSections()` builds the single-run charts for
a platform page; both return `Section[]`, which `ChartSection.astro` renders. Helpers already exist
for the common shapes — `lineSpec`, `coloredBarSpec`, `groupedSpec`, `headroomSpec`, `statTable` —
so add a chart by composing those rather than hand-rolling an ECharts option object. Every chart
carries a summary table, not 900 raw rows.

To surface a metric that is not exported yet, add it to `TIMESERIES_METRICS` in
`export_site_data.py` and give it a display name in `METRIC_LABELS` in `utils.py`, then re-export.

**The docs pages under `src/content/docs/docs/` are hand-maintained forks of the markdown in the
repo's top-level `docs/`**, with Starlight frontmatter and reworked headings. They are not synced:
editing `docs/practitioners_guide.md` does not change the website, and vice versa. Update both when
the content is meant to match.

## Assets

`site/public/images/` and the copy of the report PDF in `site/public/` are **gitignored**. They are
populated at build time by [`scripts/sync-assets.mjs`](scripts/sync-assets.mjs), which copies the
canonical files from `docs/`.

Do not add a file to `site/public/images/` directly — it will work locally and vanish in CI. Put the
canonical copy in `docs/images/` and add an entry to the `assets` array in that script. A missing
source is a hard build failure rather than a warning, so a broken reference surfaces in CI instead of
on the published page.

## The social card

`site/public/og.png` is generated by `node scripts/make-og-image.mjs` (run from `site/`), which reads
its headline figures from `src/data/runs.json` so the card cannot drift from the results. It needs a
local Chrome or Chromium, and its output is committed, so CI never runs it.

Re-run it, and commit the result, whenever the headline numbers change:

```sh
cd site && node scripts/make-og-image.mjs
```

Unlike the rest of the site, its `CARDS` array names run ids and hex colors literally
(`max_power__amd_strix_halo`, …). Adding a platform or renaming a run does not update the card — edit
that array. The colors there are also literal hex rather than the `--series-*` tokens, because the
card is rasterized outside the page; keep them in step with `src/styles/tokens.css` by hand.

The mark it draws comes from `public/images/opennav-mark.png`, which is synced from `docs/images/`,
so run a build (or `npm run sync-assets`) at least once in a fresh clone before generating the card.

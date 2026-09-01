/**
 * Typed access to the dataset produced by
 * opennav_benchmark_analysis/export_site_data.py.
 *
 * Nothing here enumerates benchmark categories. The category list comes from
 * the data, so publishing a new one is an exporter change alone.
 */

import categoriesJson from '../data/categories.json';
import runsJson from '../data/runs.json';
import derivedJson from '../data/derived.json';
import platformsJson from '../data/platforms.json';

export interface Category {
  key: string;
  label: string;
  order: number;
  description: string;
  run_keys: string[];
}

export interface StatBlock {
  label: string;
  mean: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
  p50: number | null;
  p95: number | null;
  p99: number | null;
}

export interface VlmSummary {
  total: number;
  success: number;
  error: number;
  cancelled: number;
  retries_exhausted: number;
  no_image: number;
  stale_image: number;
  encode_failed: number;
  mean_duration_sec: number;
  mean_success_duration_sec: number;
  p95_success_duration_sec: number;
  durations_sec: number[];
  success_durations_sec: number[];
}

export interface Application {
  completed_missions: number;
  control_loop_misses: number;
  control_loop_misses_per_sec: number | null;
  control_loop_target_hz: number;
  planner_cycle_sec?: Record<string, number>;
  vlm?: VlmSummary;
}

export interface Derived {
  num_cores: number;
  cpu_mean_percent: number;
  cpu_available_percent: number;
  free_core_equivalents: number;
  cpu_freq_ghz: number;
  total_ghz_cores: number;
  used_ghz_cores: number;
  available_ghz_cores: number;
  gpu_mean_percent: number;
  gpu_available_percent: number;
  least_loaded_core_percent?: number;
  single_thread_headroom_ghz?: number;
  ram_mean_percent: number;
  ram_available_percent: number;
  ram_total_mb?: number;
  ram_used_mb?: number;
  ram_free_mb?: number;
  vram_total_mb?: number;
  vram_used_mb?: number;
  vram_free_mb?: number;
  vram_free_percent?: number;
  mean_power_w?: number;
  ghz_cores_per_watt?: number;
  gpu_percent_per_watt?: number;
  cpu_thermal_margin_c?: number;
  gpu_thermal_margin_c?: number;
}

export interface Run {
  id: string;
  category: string;
  run_key: string;
  platform: string;
  platform_label: string;
  label: string;
  tdp_w: number | null;
  note: string;
  log_dir: string;
  duration_sec: number;
  actual_samples: number;
  application: Application;
  derived: Derived;
  stats: Record<string, StatBlock>;
}

export interface Platform {
  key: string;
  slug: string;
  label: string;
  short_label: string;
  tile_label: string;
  vendor: string;
  vendor_url: string;
  summary: string;
  spec: Record<string, string>;
  as_tested: Record<string, string>;
  sensor_driver_load: Record<string, number>;
}

export interface Timeseries {
  elapsed_sec: number[];
  metrics: Record<string, (number | null)[]>;
  cores?: { count: number; matrix: number[][] };
  core_histogram?: { bins: number[]; counts: number[] };
  core_percentiles?: Record<string, number[]>;
  peak_core_index?: number;
  core_means?: number[];
  rolling_std?: { window: number; series: Record<string, (number | null)[]> };
}

export const categories = (categoriesJson as Category[])
  .slice()
  .sort((a, b) => a.order - b.order);

export const runs = runsJson as unknown as Run[];

export const derived = derivedJson as Record<
  string,
  {
    radar: {
      dimensions: string[];
      raw: Record<string, Record<string, number>>;
      normalized: Record<string, Record<string, number>>;
    };
    efficiency: Record<string, Derived & { label: string; platform: string }>;
  }
>;

export const platforms = platformsJson.platforms as unknown as Record<string, Platform>;
export const platformOrder = platformsJson.order as string[];
export const metricLabels = platformsJson.metric_labels as Record<string, string>;

/** All runs in a category, in the canonical platform order. */
export function runsFor(categoryKey: string): Run[] {
  return runs
    .filter((r) => r.category === categoryKey)
    .sort(
      (a, b) =>
        platformOrder.indexOf(a.platform) - platformOrder.indexOf(b.platform) ||
        (b.tdp_w ?? 0) - (a.tdp_w ?? 0),
    );
}

/** Every run of one platform, across all published categories. */
export function runsForPlatform(platformKey: string): Run[] {
  return runs
    .filter((r) => r.platform === platformKey)
    .sort(
      (a, b) =>
        categories.findIndex((c) => c.key === a.category) -
        categories.findIndex((c) => c.key === b.category),
    );
}

export function categoryFor(key: string): Category {
  const found = categories.find((c) => c.key === key);
  if (!found) throw new Error(`unknown category: ${key}`);
  return found;
}

export function platformFor(key: string): Platform {
  const found = platforms[key];
  if (!found) throw new Error(`unknown platform: ${key}`);
  return found;
}

/** The default category shown when the reader has not chosen one. */
export const defaultCategory = categories[0];

/**
 * CSS variable holding each platform's series color. One hue per platform,
 * used identically on every chart site-wide. TDP variants of the same
 * platform share the hue and are separated by a dashed stroke.
 *
 * Adding a platform means adding an entry here AND defining the variable in
 * all three theme blocks of styles/tokens.css. Miss either and the platform
 * renders in --series-neutral grey rather than failing, so check a chart and
 * a results table after adding one. See site/README.md.
 */
export const seriesVar: Record<string, string> = {
  amd_strix_halo: '--series-amd',
  jetson_thor: '--series-thor',
  jetson_orin: '--series-orin',
};

export function colorFor(platformKey: string): string {
  return `var(${seriesVar[platformKey] ?? '--series-neutral'})`;
}

/** True for a run that is a secondary TDP variant of its platform. */
export function isVariant(run: Run, all: Run[]): boolean {
  const sameplat = all.filter((r) => r.platform === run.platform);
  if (sameplat.length < 2) return false;
  const primary = sameplat.reduce((a, b) => ((a.tdp_w ?? 0) >= (b.tdp_w ?? 0) ? a : b));
  return primary.id !== run.id;
}

/** Timeseries files, eagerly imported so pages can pick by key at build time. */
const timeseriesModules = import.meta.glob<Timeseries>('../data/timeseries/*.json', {
  eager: true,
  import: 'default',
});

export function timeseriesFor(runId: string): Timeseries | null {
  const match = Object.entries(timeseriesModules).find(([path]) =>
    path.endsWith(`/${runId}.json`),
  );
  return match ? (match[1] as Timeseries) : null;
}

/** Keep every point up to `target`, then take an evenly spaced subset. */
export function decimate<T>(values: T[], target = 300): T[] {
  if (values.length <= target) return values;
  const step = Math.ceil(values.length / target);
  return values.filter((_, i) => i % step === 0);
}

/** Formats a number for display. Missing values render as "n/a". */
export function fmt(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'n/a';
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

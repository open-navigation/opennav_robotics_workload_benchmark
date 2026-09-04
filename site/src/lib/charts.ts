/**
 * Chart definitions.
 *
 * Every chart the analysis pipeline produces has an entry here. Charts are
 * grouped into sections; each section has exactly one headline chart shown
 * expanded, and the rest expand on demand. There is one idea per chart, so
 * multi-panel figures from the Plotly pipeline are split into separate charts
 * rather than merged, and no chart carries two y-scales.
 */

import {
  decimate,
  fmt,
  isVariant,
  seriesVar,
  timeseriesFor,
  type Run,
  type Timeseries,
} from './data';

export interface ChartDef {
  id: string;
  title: string;
  takeaway?: string;
  spec: unknown;
  table: { columns: string[]; rows: (string | number | null)[][]; numeric?: number[] };
  tableCaption?: string;
  sources: string[];
  csv: string[];
  height?: number;
  /** Render beside the headline chart rather than behind the disclosure. */
  inline?: boolean;
}

export interface Section {
  id: string;
  title: string;
  /** Icon name from the Icon component's set. */
  icon: string;
  lede: string;
  headline: ChartDef;
  supporting: ChartDef[];
}

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

function csvFor(runs: Run[]): string[] {
  return runs.map((r) => `${BASE}/data/csv/${r.id}.csv`);
}

function sourcesFor(runs: Run[]): string[] {
  return runs.map((r) => r.log_dir);
}

function ts(run: Run): Timeseries | null {
  return timeseriesFor(run.id);
}

/** Line-chart spec over a 1 Hz metric, decimated for the wire. */
function lineSpec(runs: Run[], metric: string, yName: string, unit: string, digits = 1) {
  const first = ts(runs[0]);
  const x = decimate(first?.elapsed_sec ?? []).map(String);
  return {
    kind: 'line',
    x,
    xName: 'Elapsed time (s)',
    yName,
    unit,
    digits,
    series: runs
      .filter((r) => ts(r)?.metrics[metric])
      .map((r) => ({
        name: r.label,
        colorVar: seriesVarName(r, runs),
        dashed: isVariant(r, runs),
        data: decimate(ts(r)!.metrics[metric]),
      })),
  };
}

function seriesVarName(run: Run, all: Run[]): string {
  void all;
  return seriesVar[run.platform] ?? '--series-neutral';
}

/** Summary table for a time-series chart: distribution, not 900 raw rows. */
function statTable(runs: Run[], metric: string, unit: string) {
  return {
    columns: ['Platform', `Mean (${unit})`, `p50 (${unit})`, `p95 (${unit})`, `Max (${unit})`],
    rows: runs
      .filter((r) => r.stats[metric])
      .map((r) => [
        r.label,
        fmt(r.stats[metric].mean, 2),
        fmt(r.stats[metric].p50, 2),
        fmt(r.stats[metric].p95, 2),
        fmt(r.stats[metric].max, 2),
      ]),
  };
}

/**
 * ECharts cannot read a CSS variable out of a data item, so per-bar colors are
 * resolved by name here into the spec the runtime consumes.
 */
function coloredBarSpec(
  runs: Run[],
  values: (r: Run) => number | null | undefined,
  yName: string,
  unit: string,
  digits = 1,
) {
  const present = runs.filter((r) => {
    const v = values(r);
    return v !== null && v !== undefined;
  });
  return {
    kind: 'bar',
    overlap: true,
    x: present.map((r) => r.label),
    yName,
    unit,
    digits,
    series: present.map((r) => ({
      name: r.label,
      colorVar: seriesVarName(r, runs),
      dashed: isVariant(r, runs),
      // one bar per series so each carries its platform's hue
      data: present.map((other) => (other.id === r.id ? values(r) : null)),
      labels: present.map((other) =>
        other.id === r.id ? `${fmt(values(r), digits)}${unit ? ' ' + unit : ''}` : '',
      ),
    })),
  };
}

/** Grouped bar across a fixed set of categories, one series per platform. */
function groupedSpec(
  runs: Run[],
  categories: string[],
  value: (r: Run, category: string, i: number) => number | null,
  yName: string,
  unit: string,
  digits = 1,
) {
  return {
    kind: 'bar',
    x: categories,
    yName,
    unit,
    digits,
    series: runs.map((r) => ({
      name: r.label,
      colorVar: seriesVarName(r, runs),
      dashed: isVariant(r, runs),
      data: categories.map((c, i) => value(r, c, i)),
    })),
  };
}

/** Used vs available, stacked, with the available half faded. */
function headroomSpec(
  runs: Run[],
  used: (r: Run) => number,
  free: (r: Run) => number,
  yName: string,
  unit: string,
  digits = 1,
) {
  return {
    kind: 'stacked',
    overlap: true,
    noLegend: true,
    x: runs.map((r) => r.label),
    yName,
    unit,
    digits,
    series: [
      ...runs.map((r) => ({
        name: `${r.label}, used`,
        colorVar: seriesVarName(r, runs),
        stack: 'total',
        data: runs.map((o) => (o.id === r.id ? used(r) : null)),
        labels: runs.map((o) => (o.id === r.id ? `${fmt(used(r), digits)}` : '')),
      })),
      ...runs.map((r) => ({
        name: `${r.label}, available`,
        colorVar: seriesVarName(r, runs),
        faded: true,
        stack: 'total',
        data: runs.map((o) => (o.id === r.id ? free(r) : null)),
        labels: runs.map((o) => (o.id === r.id ? `${fmt(free(r), digits)} free` : '')),
      })),
    ],
  };
}

// ---------------------------------------------------------------------------
// Comparison sections
// ---------------------------------------------------------------------------

export function comparisonSections(
  runs: Run[],
  radar: { dimensions: string[]; normalized: Record<string, Record<string, number>> },
): Section[] {
  const src = sourcesFor(runs);
  const csv = csvFor(runs);

  // -- Overview -------------------------------------------------------------

  // With one run there is nothing to normalize against, so every axis scores
  // 1.0 and the shape is full by construction. Say so, or the reader mistakes
  // a degenerate plot for a perfect score.
  const soloRadar = runs.filter((r) => radar.normalized[r.run_key]).length < 2;

  const radarChart: ChartDef = {
    id: 'platform-balance-radar',
    title: 'Platform balance',
    takeaway: soloRadar
      ? 'Six dimensions, normalized within this category. Only one run is published here, ' +
        'so every axis normalizes against itself and reads 1.0 — the full shape shows the ' +
        'axes, not a perfect score. Compare against the max power category instead.'
      : 'Six dimensions, each min-max normalized against the strongest platform in this category.',
    height: 420,
    spec: {
      kind: 'radar',
      indicators: radar.dimensions.map((d) => ({ name: d, max: 1 })),
      series: runs
        .filter((r) => radar.normalized[r.run_key])
        .map((r) => ({
          name: r.label,
          colorVar: seriesVarName(r, runs),
          dashed: isVariant(r, runs),
          data: radar.dimensions.map((d) => radar.normalized[r.run_key][d]),
        })),
    },
    table: {
      columns: ['Platform', ...radar.dimensions],
      rows: runs
        .filter((r) => radar.normalized[r.run_key])
        .map((r) => [r.label, ...radar.dimensions.map((d) => fmt(radar.normalized[r.run_key][d], 2))]),
    },
    tableCaption: soloRadar
      ? 'Normalized 0–1 within this category. With a single run every axis is 1.0 by construction.'
      : 'Normalized 0–1 against the best platform on each axis; higher is better.',
    sources: src,
    csv,
  };

  const overview: Section = {
    id: 'overview',
    icon: 'layers',
    title: 'Overview',
    lede:
      'Where each platform sits across the whole workload before drilling into any one ' +
      'resource.',
    headline: radarChart,
    supporting: [
      {
        id: 'mean-utilization',
        inline: true,
        title: 'Mean utilization by resource',
        takeaway:
          'Mean utilization of each resource across the run, sampled once a second.',
        spec: groupedSpec(
          runs,
          ['CPU', 'GPU', 'RAM'],
          (r, _c, i) =>
            [r.derived.cpu_mean_percent, r.derived.gpu_mean_percent, r.derived.ram_mean_percent][i],
          'Mean utilization (%)',
          '%',
        ),
        table: {
          columns: ['Platform', 'CPU (%)', 'GPU (%)', 'RAM (%)'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.derived.cpu_mean_percent),
            fmt(r.derived.gpu_mean_percent),
            fmt(r.derived.ram_mean_percent),
          ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'resource-headroom',
        inline: true,
        title: 'CPU headroom, used against available',
        takeaway:
          'The faded portion is what is left for the application developer once the ' +
          'navigation and AI workload is running.',
        spec: headroomSpec(
          runs,
          (r) => r.derived.cpu_mean_percent,
          (r) => r.derived.cpu_available_percent,
          'CPU (%)',
          '%',
        ),
        table: {
          columns: ['Platform', 'Used (%)', 'Available (%)', 'Total cores', 'Free core equiv.'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.derived.cpu_mean_percent),
            fmt(r.derived.cpu_available_percent),
            r.derived.num_cores,
            fmt(r.derived.free_core_equivalents),
          ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'summary-power',
        inline: true,
        title: 'Mean board power',
        takeaway: 'Measured at the board, averaged across the run.',
        spec: coloredBarSpec(runs, (r) => r.derived.mean_power_w, 'Board power (W)', 'W'),
        table: {
          columns: ['Platform', 'Configured TDP (W)', 'Mean (W)', 'p95 (W)', 'Max (W)'],
          rows: runs.map((r) => {
            const key = r.stats.board_power_w ? 'board_power_w' : 'gpu_power_w';
            return [
              r.label,
              r.tdp_w ?? 'n/a',
              fmt(r.derived.mean_power_w),
              fmt(r.stats[key]?.p95),
              fmt(r.stats[key]?.max),
            ];
          }),
        },
        sources: src,
        csv,
      },
      {
        id: 'summary-thermal',
        inline: true,
        title: 'Mean CPU and GPU temperature',
        takeaway: 'Steady-state package temperatures under the composed workload.',
        spec: groupedSpec(
          runs,
          ['CPU', 'GPU'],
          (r, _c, i) => [r.stats.cpu_temp?.mean ?? null, r.stats.gpu_temp?.mean ?? null][i],
          'Temperature (°C)',
          '°C',
        ),
        table: {
          columns: ['Platform', 'CPU mean (°C)', 'CPU max (°C)', 'GPU mean (°C)', 'GPU max (°C)'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.stats.cpu_temp?.mean),
            fmt(r.stats.cpu_temp?.max),
            fmt(r.stats.gpu_temp?.mean),
            fmt(r.stats.gpu_temp?.max),
          ]),
        },
        sources: src,
        csv,
      },
    ],
  };

  // -- Application performance ---------------------------------------------

  const application: Section = {
    id: 'application',
    icon: 'robot',
    title: 'Application performance',
    lede:
      'What the robot actually achieved. A platform that looks healthy on utilization ' +
      'counters but misses its control deadlines is not a platform you can ship.',
    headline: {
      id: 'completed-missions',
      title: 'Completed missions',
      takeaway:
        'Navigation goals that reached "Goal succeeded" within the run, counted from the ' +
        'ROS logs.',
      spec: coloredBarSpec(runs, (r) => r.application.completed_missions, 'Missions completed', '', 0),
      table: {
        columns: ['Platform', 'Missions completed', 'Run duration (s)'],
        rows: runs.map((r) => [r.label, r.application.completed_missions, r.duration_sec]),
      },
      tableCaption: 'Counted from [bt_navigator]: Goal succeeded lines in the ROS logs.',
      sources: src,
      csv,
    },
    supporting: [
      {
        id: 'control-loop-misses',
        inline: true,
        title: 'Control loop misses per second',
        takeaway: `The Nav2 controller server targets ${runs[0].application.control_loop_target_hz} Hz; each miss is a control cycle that did not complete on time.`,
        spec: coloredBarSpec(
          runs,
          (r) => r.application.control_loop_misses_per_sec,
          'Misses per second',
          '/s',
          2,
        ),
        table: {
          columns: ['Platform', 'Misses per second', 'Total misses', 'Target rate (Hz)'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.application.control_loop_misses_per_sec, 2),
            r.application.control_loop_misses,
            r.application.control_loop_target_hz,
          ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'planner-cycle-times',
        inline: true,
        title: 'Planner cycle time',
        takeaway:
          'Time to produce one Hybrid-A* plan with full-footprint SE2 collision checking, ' +
          'derived from the planner server loop-rate warnings.',
        spec: groupedSpec(
          runs.filter((r) => r.application.planner_cycle_sec),
          ['p50', 'p95', 'p99'],
          (r, c) => (r.application.planner_cycle_sec?.[c] ?? 0) * 1000,
          'Cycle time (ms)',
          'ms',
          0,
        ),
        table: {
          columns: ['Platform', 'Samples', 'Mean (ms)', 'p50 (ms)', 'p95 (ms)', 'p99 (ms)'],
          rows: runs
            .filter((r) => r.application.planner_cycle_sec)
            .map((r) => {
              const p = r.application.planner_cycle_sec!;
              return [
                r.label,
                p.count,
                fmt(p.mean * 1000, 0),
                fmt(p.p50 * 1000, 0),
                fmt(p.p95 * 1000, 0),
                fmt(p.p99 * 1000, 0),
              ];
            }),
        },
        sources: src,
        csv,
      },
      {
        id: 'vlm-query-outcomes',
        inline: true,
        title: 'VLM query outcomes',
        takeaway:
          'Scene-understanding queries issued into the navigation behavior tree, and how ' +
          'many of them returned an answer the tree could use.',
        spec: {
          kind: 'stacked',
          x: runs.filter((r) => r.application.vlm).map((r) => r.label),
          yName: 'Queries',
          unit: '',
          digits: 0,
          series: (['success', 'error', 'cancelled'] as const).map((outcome, i) => ({
            name: outcome[0].toUpperCase() + outcome.slice(1),
            colorVar: ['--series-thor', '--series-amd', '--series-neutral'][i],
            stack: 'total',
            data: runs.filter((r) => r.application.vlm).map((r) => r.application.vlm![outcome]),
          })),
        },
        table: {
          columns: ['Platform', 'Total', 'Success', 'Error', 'Cancelled'],
          rows: runs
            .filter((r) => r.application.vlm)
            .map((r) => [
              r.label,
              r.application.vlm!.total,
              r.application.vlm!.success,
              r.application.vlm!.error,
              r.application.vlm!.cancelled,
            ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'vlm-latency',
        title: 'VLM query latency',
        takeaway:
          'Wall-clock time for a successful query, from request to a parsed answer. Only ' +
          'platforms that completed at least one query appear.',
        spec: groupedSpec(
          runs.filter((r) => r.application.vlm && r.application.vlm.success > 0),
          ['Mean', 'p95'],
          (r, _c, i) =>
            [
              r.application.vlm!.mean_success_duration_sec,
              r.application.vlm!.p95_success_duration_sec,
            ][i],
          'Duration (s)',
          's',
        ),
        table: {
          columns: ['Platform', 'Successful queries', 'Mean (s)', 'p95 (s)'],
          rows: runs
            .filter((r) => r.application.vlm)
            .map((r) => [
              r.label,
              r.application.vlm!.success,
              r.application.vlm!.success > 0 ? fmt(r.application.vlm!.mean_success_duration_sec, 2) : 'n/a',
              r.application.vlm!.success > 0 ? fmt(r.application.vlm!.p95_success_duration_sec, 2) : 'n/a',
            ]),
        },
        sources: src,
        csv,
      },
    ],
  };

  // -- CPU ------------------------------------------------------------------

  const perCoreRows = runs.map((r) => {
    const t = ts(r);
    const means = t?.core_means ?? [];
    const peak = means.length ? Math.max(...means) : null;
    return [
      r.label,
      r.derived.num_cores,
      fmt(r.derived.cpu_mean_percent),
      peak === null ? 'n/a' : fmt(peak),
      means.length ? means.map((m, i) => [i, m] as [number, number]).filter(([, m]) => m > 60).map(([i]) => i).join(', ') || 'none' : 'n/a',
    ];
  });

  const maxCores = Math.max(...runs.map((r) => ts(r)?.cores?.count ?? 0));

  const cpu: Section = {
    id: 'cpu',
    icon: 'cpu',
    title: 'CPU',
    lede:
      'Total load, how it is distributed across cores, and how much clock is behind it. ' +
      'A workload spread evenly across many cores behaves very differently from the same ' +
      'total load piled onto a few.',
    headline: {
      id: 'cpu-comparison',
      title: 'CPU utilization over the run',
      takeaway:
        'Total CPU utilization across all cores, sampled once a second for the length of ' +
        'the run.',
      spec: lineSpec(runs, 'cpu_total', 'CPU utilization (%)', '%'),
      table: statTable(runs, 'cpu_total', '%'),
      sources: src,
      csv,
    },
    supporting: [
      {
        id: 'peak-core-loading',
        title: 'Per-core mean utilization',
        takeaway:
          'One point per physical core. Flat lines mean the workload spread; spikes mean ' +
          'individual cores are pinned and are the ones that will miss deadlines first.',
        spec: {
          kind: 'line',
          x: Array.from({ length: maxCores }, (_, i) => String(i)),
          xName: 'Core index',
          yName: 'Mean utilization (%)',
          unit: '%',
          digits: 1,
          series: runs
            .filter((r) => ts(r)?.core_means)
            .map((r) => ({
              name: r.label,
              colorVar: seriesVarName(r, runs),
              dashed: isVariant(r, runs),
              data: ts(r)!.core_means!,
            })),
        },
        table: {
          columns: ['Platform', 'Cores', 'Mean CPU (%)', 'Busiest core (%)', 'Cores above 60%'],
          rows: perCoreRows,
        },
        sources: src,
        csv,
      },
      {
        id: 'core-utilization-percentiles',
        title: 'Per-core utilization percentiles',
        takeaway:
          'The distribution of individual core loads. A high p99 with a low p50 is the ' +
          'signature of a few saturated cores inside an otherwise idle package.',
        spec: groupedSpec(
          runs,
          ['p50', 'p95', 'p99'],
          (r, c) => {
            const p = ts(r)?.core_percentiles?.[c];
            return p ? p.reduce((a, b) => a + b, 0) / p.length : null;
          },
          'Per-core utilization (%)',
          '%',
        ),
        table: {
          columns: ['Platform', 'p50 (%)', 'p95 (%)', 'p99 (%)'],
          rows: runs.map((r) => {
            const pc = ts(r)?.core_percentiles;
            const avg = (k: string) => {
              const arr = pc?.[k];
              return arr ? fmt(arr.reduce((a, b) => a + b, 0) / arr.length) : 'n/a';
            };
            return [r.label, avg('p50'), avg('p95'), avg('p99')];
          }),
        },
        sources: src,
        csv,
      },
      {
        id: 'cpu-core-histogram',
        title: 'Per-core utilization distribution',
        takeaway:
          'Every per-core sample in the run, bucketed. Mass on the left is idle silicon ' +
          'available to the application; mass on the right is silicon already spoken for.',
        spec: {
          kind: 'histogram',
          x: (ts(runs[0])?.core_histogram?.bins ?? []).slice(0, -1).map((b) => `${b}–${b + 5}`),
          xName: 'Core utilization (%)',
          yName: 'Share of samples (%)',
          unit: '%',
          digits: 1,
          series: runs
            .filter((r) => ts(r)?.core_histogram)
            .map((r) => {
              const h = ts(r)!.core_histogram!;
              const total = h.counts.reduce((a, b) => a + b, 0) || 1;
              return {
                name: r.label,
                colorVar: seriesVarName(r, runs),
                data: h.counts.map((c) => Number(((c / total) * 100).toFixed(2))),
              };
            }),
        },
        table: {
          columns: ['Platform', 'Samples below 5%', 'Samples above 60%', 'Total samples'],
          rows: runs
            .filter((r) => ts(r)?.core_histogram)
            .map((r) => {
              const h = ts(r)!.core_histogram!;
              const total = h.counts.reduce((a, b) => a + b, 0);
              const below = h.counts[0];
              const above = h.counts.slice(12).reduce((a, b) => a + b, 0);
              return [
                r.label,
                `${fmt((below / total) * 100)}%`,
                `${fmt((above / total) * 100)}%`,
                total,
              ];
            }),
        },
        sources: src,
        csv,
      },
      {
        id: 'cpu-frequency',
        title: 'CPU clock frequency',
        takeaway:
          'Sustained clock under load. Clock and core count together set how much work a ' +
          'single real-time thread can finish inside its deadline.',
        spec: lineSpec(runs, 'cpu_freq_mhz', 'Clock (MHz)', 'MHz', 0),
        table: statTable(runs, 'cpu_freq_mhz', 'MHz'),
        sources: src,
        csv,
      },
    ],
  };

  // -- Headroom -------------------------------------------------------------

  const headroom: Section = {
    id: 'headroom',
    icon: 'gauge',
    title: 'Headroom',
    lede:
      'What is left over. This is the number that decides whether your perception stack, ' +
      'your fleet client, and your safety monitor also fit on the same computer.',
    headline: {
      id: 'absolute-compute-headroom',
      title: 'Absolute compute headroom',
      takeaway:
        'Free cores multiplied by sustained clock, so core count and clock speed are ' +
        'counted together.',
      spec: headroomSpec(
        runs,
        (r) => r.derived.used_ghz_cores,
        (r) => r.derived.available_ghz_cores,
        'GHz-cores',
        '',
        1,
      ),
      table: {
        columns: ['Platform', 'Total (GHz-cores)', 'Used', 'Available', 'Cores', 'Clock (GHz)'],
        rows: runs.map((r) => [
          r.label,
          fmt(r.derived.total_ghz_cores),
          fmt(r.derived.used_ghz_cores),
          fmt(r.derived.available_ghz_cores),
          r.derived.num_cores,
          fmt(r.derived.cpu_freq_ghz, 2),
        ]),
      },
      sources: src,
      csv,
    },
    supporting: [
      {
        id: 'free-core-equivalents',
        title: 'Free core equivalents',
        takeaway:
          'Available CPU expressed as whole cores, which is how you actually budget a new ' +
          'node onto the machine.',
        spec: coloredBarSpec(runs, (r) => r.derived.free_core_equivalents, 'Free cores', 'cores'),
        table: {
          columns: ['Platform', 'Total cores', 'Free core equiv.', 'Available CPU (%)'],
          rows: runs.map((r) => [
            r.label,
            r.derived.num_cores,
            fmt(r.derived.free_core_equivalents),
            fmt(r.derived.cpu_available_percent),
          ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'single-thread-headroom',
        title: 'Single-thread headroom',
        takeaway:
          'Clock available on the least-loaded core, which is the budget for one new ' +
          'real-time control thread that cannot be parallelized.',
        spec: coloredBarSpec(
          runs,
          (r) => r.derived.single_thread_headroom_ghz,
          'Available single-thread performance (GHz)',
          'GHz',
          2,
        ),
        table: {
          columns: ['Platform', 'Least-loaded core (%)', 'Clock (GHz)', 'Headroom (GHz)'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.derived.least_loaded_core_percent),
            fmt(r.derived.cpu_freq_ghz, 2),
            fmt(r.derived.single_thread_headroom_ghz, 2),
          ]),
        },
        sources: src,
        csv,
      },
    ],
  };

  // -- GPU & memory ---------------------------------------------------------

  const gpu: Section = {
    id: 'gpu-memory',
    icon: 'gpu',
    title: 'GPU and memory',
    lede:
      'The VLM is sized to saturate the GPU, so GPU utilization here reads as "kept fed", ' +
      'not as "under strain". Memory headroom decides how large a model you can host.',
    headline: {
      id: 'gpu-comparison',
      title: 'GPU utilization over the run',
      takeaway:
        'A platform pinned near 100% is fully absorbing the AI workload; a low figure ' +
        'means the GPU is starved because the CPU cannot feed it.',
      spec: lineSpec(runs, 'gpu_util', 'GPU utilization (%)', '%'),
      table: statTable(runs, 'gpu_util', '%'),
      sources: src,
      csv,
    },
    supporting: [
      {
        id: 'gpu-effective-throughput',
        title: 'GPU effective throughput',
        takeaway:
          'Utilization multiplied by clock, which separates a GPU that is busy at a high ' +
          'clock from one that is busy at a throttled one.',
        spec: lineSpec(runs, 'gpu_effective_throughput', 'Effective throughput (GHz)', 'GHz'),
        table: statTable(runs, 'gpu_effective_throughput', 'GHz'),
        sources: src,
        csv,
      },
      {
        id: 'gpu-clock-speed',
        title: 'GPU clock frequency',
        takeaway: 'Sustained GPU clock, the second half of effective throughput.',
        spec: lineSpec(runs, 'gpu_clock_mhz', 'GPU clock (MHz)', 'MHz', 0),
        table: statTable(runs, 'gpu_clock_mhz', 'MHz'),
        sources: src,
        csv,
      },
      {
        id: 'gpu-memory-headroom',
        title: 'Memory headroom',
        takeaway:
          'System memory used against free. On unified-memory parts the free portion is ' +
          'directly available to the GPU, which is what sets the largest model you can serve.',
        spec: headroomSpec(
          runs.filter((r) => r.derived.ram_total_mb),
          (r) => (r.derived.ram_used_mb ?? 0) / 1024,
          (r) => (r.derived.ram_free_mb ?? 0) / 1024,
          'Memory (GB)',
          'GB',
        ),
        table: {
          columns: ['Platform', 'Total (GB)', 'Used (GB)', 'Free (GB)', 'VRAM used (MB)', 'VRAM free (MB)'],
          rows: runs.map((r) => [
            r.label,
            fmt((r.derived.ram_total_mb ?? 0) / 1024),
            fmt((r.derived.ram_used_mb ?? 0) / 1024),
            fmt((r.derived.ram_free_mb ?? 0) / 1024),
            r.derived.vram_used_mb ? fmt(r.derived.vram_used_mb, 0) : 'n/a',
            r.derived.vram_free_mb ? fmt(r.derived.vram_free_mb, 0) : 'n/a',
          ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'ram-comparison',
        title: 'System memory utilization over the run',
        takeaway: 'Memory pressure across the run, including any swap the platform resorted to.',
        spec: lineSpec(runs, 'ram_percent', 'RAM utilization (%)', '%'),
        table: {
          ...statTable(runs, 'ram_percent', '%'),
          columns: ['Platform', 'Mean (%)', 'p50 (%)', 'p95 (%)', 'Max (%)'],
        },
        sources: src,
        csv,
      },
    ],
  };

  // -- Power & thermal ------------------------------------------------------

  const power: Section = {
    id: 'power-thermal',
    icon: 'power',
    title: 'Power and thermal',
    lede:
      'Efficiency at the board level, and how much thermal margin is left before the ' +
      'platform starts throttling in a sealed robot enclosure.',
    headline: {
      id: 'performance-per-watt',
      title: 'Available compute per watt',
      takeaway: 'Free GHz-cores divided by mean board power.',
      spec: coloredBarSpec(
        runs,
        (r) => r.derived.ghz_cores_per_watt,
        'Available compute per watt (GHz-cores/W)',
        '',
        3,
      ),
      table: {
        columns: ['Platform', 'Available (GHz-cores)', 'Mean power (W)', 'GHz-cores/W'],
        rows: runs.map((r) => [
          r.label,
          fmt(r.derived.available_ghz_cores),
          fmt(r.derived.mean_power_w),
          fmt(r.derived.ghz_cores_per_watt, 3),
        ]),
      },
      sources: src,
      csv,
    },
    supporting: [
      {
        id: 'gpu-per-watt',
        title: 'GPU utilization per watt',
        takeaway:
          'GPU-only efficiency, isolating the AI workload from the CPU side of the ' +
          'comparison.',
        spec: coloredBarSpec(runs, (r) => r.derived.gpu_percent_per_watt, 'GPU % per watt', '', 3),
        table: {
          columns: ['Platform', 'Mean GPU (%)', 'Mean power (W)', 'GPU %/W'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.derived.gpu_mean_percent),
            fmt(r.derived.mean_power_w),
            fmt(r.derived.gpu_percent_per_watt, 3),
          ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'efficiency-scatter',
        title: 'Power against available compute',
        takeaway:
          'Up and to the left is better: more headroom for fewer watts. Each point is one ' +
          'platform in this power category.',
        spec: {
          kind: 'scatter',
          xName: 'Mean board power (W)',
          yName: 'Available compute (GHz-cores)',
          series: runs
            .filter((r) => r.derived.mean_power_w)
            .map((r) => ({
              name: r.label,
              colorVar: seriesVarName(r, runs),
              data: [[r.derived.mean_power_w!, r.derived.available_ghz_cores]],
            })),
        },
        table: {
          columns: ['Platform', 'Mean power (W)', 'Available (GHz-cores)'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.derived.mean_power_w),
            fmt(r.derived.available_ghz_cores),
          ]),
        },
        sources: src,
        csv,
      },
      {
        id: 'power-comparison',
        title: 'Board power over the run',
        takeaway: 'Instantaneous board draw, showing how each platform tracks its configured TDP.',
        spec: lineSpec(
          runs,
          runs[0].stats.board_power_w ? 'board_power_w' : 'gpu_power_w',
          'Board power (W)',
          'W',
        ),
        table: {
          columns: ['Platform', 'Configured TDP (W)', 'Mean (W)', 'p95 (W)', 'Max (W)'],
          rows: runs.map((r) => {
            const key = r.stats.board_power_w ? 'board_power_w' : 'gpu_power_w';
            return [
              r.label,
              r.tdp_w ?? 'n/a',
              fmt(r.stats[key]?.mean),
              fmt(r.stats[key]?.p95),
              fmt(r.stats[key]?.max),
            ];
          }),
        },
        sources: src,
        csv,
      },
      {
        id: 'cpu-temperature',
        title: 'CPU temperature over the run',
        takeaway: 'Package temperature under sustained load.',
        spec: lineSpec(runs, 'cpu_temp', 'CPU temperature (°C)', '°C'),
        table: statTable(runs, 'cpu_temp', '°C'),
        sources: src,
        csv,
      },
      {
        id: 'gpu-temperature',
        title: 'GPU temperature over the run',
        takeaway: 'GPU die temperature with the VLM saturating the accelerator.',
        spec: lineSpec(runs, 'gpu_temp', 'GPU temperature (°C)', '°C'),
        table: statTable(runs, 'gpu_temp', '°C'),
        sources: src,
        csv,
      },
      {
        id: 'thermal-runway',
        title: 'Thermal runway',
        takeaway:
          'Margin to a 100 °C throttle point. Small margins on a bench become no margin ' +
          'inside a sealed robot enclosure in a warm warehouse.',
        spec: groupedSpec(
          runs,
          ['CPU', 'GPU'],
          (r, _c, i) =>
            [r.derived.cpu_thermal_margin_c ?? null, r.derived.gpu_thermal_margin_c ?? null][i],
          'Margin to throttle (°C)',
          '°C',
        ),
        table: {
          columns: ['Platform', 'CPU margin (°C)', 'GPU margin (°C)'],
          rows: runs.map((r) => [
            r.label,
            fmt(r.derived.cpu_thermal_margin_c),
            fmt(r.derived.gpu_thermal_margin_c),
          ]),
        },
        sources: src,
        csv,
      },
    ],
  };

  return [overview, application, cpu, headroom, gpu, power];
}

// ---------------------------------------------------------------------------
// Single-run sections (one platform, one category)
// ---------------------------------------------------------------------------

function runLine(run: Run, metric: string, yName: string, unit: string, digits = 1) {
  const t = ts(run)!;
  return {
    kind: 'line',
    x: decimate(t.elapsed_sec).map(String),
    xName: 'Elapsed time (s)',
    yName,
    unit,
    digits,
    series: [
      {
        name: yName,
        colorVar: seriesVarName(run, [run]),
        data: decimate(t.metrics[metric] ?? []),
      },
    ],
  };
}

function runStatTable(run: Run, metrics: [string, string][]) {
  return {
    columns: ['Metric', 'Mean', 'p50', 'p95', 'Max'],
    rows: metrics
      .filter(([m]) => run.stats[m])
      .map(([m, label]) => [
        label,
        fmt(run.stats[m].mean, 2),
        fmt(run.stats[m].p50, 2),
        fmt(run.stats[m].p95, 2),
        fmt(run.stats[m].max, 2),
      ]),
  };
}

export function singleRunSections(run: Run): Section[] {
  const t = ts(run);
  if (!t) return [];
  const src = [run.log_dir];
  const csv = [`${BASE}/data/csv/${run.id}.csv`];
  const has = (m: string) => Boolean(t.metrics[m]);

  const sections: Section[] = [];

  // -- CPU ------------------------------------------------------------------
  const heatmapCols = decimate(t.elapsed_sec, 120);
  const colStep = Math.max(1, Math.ceil(t.elapsed_sec.length / 120));
  const heatData: number[][] = [];
  if (t.cores) {
    t.cores.matrix.forEach((coreRow, coreIdx) => {
      coreRow.forEach((v, sampleIdx) => {
        if (sampleIdx % colStep === 0) {
          heatData.push([Math.floor(sampleIdx / colStep), coreIdx, Math.round(v)]);
        }
      });
    });
  }

  sections.push({
    id: 'run-cpu',
    icon: 'cpu',
    title: 'CPU',
    lede: 'Total load, its distribution across cores, and the clock behind it.',
    headline: {
      id: `${run.id}-cpu-total`,
      title: 'CPU utilization',
      takeaway:
        'Total CPU utilization across all cores, sampled once a second for the length of ' +
        'the run.',
      spec: runLine(run, 'cpu_total', 'CPU utilization (%)', '%'),
      table: runStatTable(run, [
        ['cpu_total', 'CPU total (%)'],
        ['peak_core_util', 'Peak core (%)'],
        ['mean_core_util', 'Mean core (%)'],
        ['cores_active_percent', 'Active cores (%)'],
      ]),
      sources: src,
      csv,
    },
    supporting: [
      ...(t.cores
        ? [
            {
              id: `${run.id}-core-heatmap`,
              title: 'Per-core utilization over time',
              takeaway:
                'One row per core. Persistent dark bands are cores that stay pinned for the ' +
                'whole run.',
              height: Math.min(520, 140 + t.cores.count * 11),
              spec: {
                kind: 'heatmap',
                xName: 'Elapsed time (s)',
                yName: 'Core',
                heatmap: {
                  rows: Array.from({ length: t.cores.count }, (_, i) => String(i)),
                  cols: heatmapCols,
                  max: 100,
                },
                series: [{ name: 'Utilization', colorVar: '--ramp-4', data: heatData }],
              },
              table: {
                columns: ['Core', 'Mean (%)'],
                rows: (t.core_means ?? []).map((m, i) => [String(i), fmt(m)]),
              },
              sources: src,
              csv,
            } as ChartDef,
            {
              id: `${run.id}-core-distribution`,
              title: 'Per-core utilization distribution',
              takeaway: 'Every per-core sample in the run, bucketed into 5% bands.',
              spec: {
                kind: 'histogram',
                x: (t.core_histogram?.bins ?? []).slice(0, -1).map((b) => `${b}–${b + 5}`),
                xName: 'Core utilization (%)',
                yName: 'Samples',
                unit: '',
                digits: 0,
                series: [
                  {
                    name: 'Samples',
                    colorVar: seriesVarName(run, [run]),
                    data: t.core_histogram?.counts ?? [],
                  },
                ],
              },
              table: {
                columns: ['Utilization band (%)', 'Samples'],
                rows: (t.core_histogram?.bins ?? [])
                  .slice(0, -1)
                  .map((b, i) => [`${b}–${b + 5}`, t.core_histogram!.counts[i]]),
              },
              sources: src,
              csv,
            } as ChartDef,
          ]
        : []),
      {
        id: `${run.id}-cpu-freq`,
        title: 'CPU clock frequency',
        takeaway: 'Sustained CPU clock frequency under load.',
        spec: runLine(run, 'cpu_freq_mhz', 'Clock (MHz)', 'MHz', 0),
        table: runStatTable(run, [['cpu_freq_mhz', 'CPU frequency (MHz)']]),
        sources: src,
        csv,
      },
    ],
  });

  // -- GPU & memory ---------------------------------------------------------
  sections.push({
    id: 'run-gpu',
    icon: 'gpu',
    title: 'GPU and memory',
    lede: 'Accelerator load from the VLM workload, and the memory it leaves behind.',
    headline: {
      id: `${run.id}-gpu-util`,
      title: 'GPU utilization',
      takeaway: 'GPU utilization while the VLM issues queries continuously.',
      spec: runLine(run, 'gpu_util', 'GPU utilization (%)', '%'),
      table: runStatTable(run, [
        ['gpu_util', 'GPU utilization (%)'],
        ['gpu_clock_mhz', 'GPU clock (MHz)'],
        ['gpu_effective_throughput', 'Effective throughput (GHz)'],
      ]),
      sources: src,
      csv,
    },
    supporting: [
      {
        id: `${run.id}-ram`,
        title: 'System memory usage',
        takeaway: 'System memory in use across the run, as a share of the total fitted.',
        spec: runLine(run, 'ram_percent', 'RAM utilization (%)', '%'),
        table: runStatTable(run, [
          ['ram_percent', 'RAM (%)'],
          ['ram_used_mb', 'RAM used (MB)'],
          ['swap_percent', 'Swap (%)'],
        ]),
        sources: src,
        csv,
      },
      ...(has('gpu_mem_used_mb')
        ? [
            {
              id: `${run.id}-vram`,
              title: 'GPU memory usage',
              takeaway: 'GPU memory in use, as reported by the platform driver.',
              spec: runLine(run, 'gpu_mem_used_mb', 'GPU memory used (MB)', 'MB', 0),
              table: runStatTable(run, [
                ['gpu_mem_used_mb', 'GPU memory used (MB)'],
                ['gpu_mem_total_mb', 'GPU memory total (MB)'],
              ]),
              sources: src,
              csv,
            } as ChartDef,
          ]
        : []),
      ...(has('mem_bandwidth_gbps')
        ? [
            {
              id: `${run.id}-mem-bandwidth`,
              title: 'Memory bandwidth',
              takeaway: 'Sustained memory traffic while the sensor pipeline and VLM both run.',
              spec: runLine(run, 'mem_bandwidth_gbps', 'Bandwidth (GB/s)', 'GB/s'),
              table: runStatTable(run, [['mem_bandwidth_gbps', 'Memory bandwidth (GB/s)']]),
              sources: src,
              csv,
            } as ChartDef,
          ]
        : []),
    ],
  });

  // -- Power & thermal ------------------------------------------------------
  const powerMetric = has('board_power_w') ? 'board_power_w' : 'gpu_power_w';
  sections.push({
    id: 'run-power',
    icon: 'power',
    title: 'Power and thermal',
    lede: 'Board draw and the thermal margin left underneath it.',
    headline: {
      id: `${run.id}-power`,
      title: 'Board power',
      takeaway: 'Board power draw across the run, against the configured TDP.',
      spec: runLine(run, powerMetric, 'Board power (W)', 'W'),
      table: runStatTable(run, [[powerMetric, 'Board power (W)']]),
      sources: src,
      csv,
    },
    supporting: [
      {
        id: `${run.id}-temps`,
        title: 'CPU and GPU temperature',
        takeaway:
          'CPU and GPU package temperature under sustained load, against a 100 °C ' +
          'throttle point.',
        spec: {
          kind: 'line',
          x: decimate(t.elapsed_sec).map(String),
          xName: 'Elapsed time (s)',
          yName: 'Temperature (°C)',
          unit: '°C',
          digits: 1,
          series: [
            {
              name: 'CPU',
              colorVar: seriesVarName(run, [run]),
              data: decimate(t.metrics.cpu_temp ?? []),
            },
            {
              name: 'GPU',
              colorVar: seriesVarName(run, [run]),
              dashed: true,
              data: decimate(t.metrics.gpu_temp ?? []),
            },
          ],
        },
        table: runStatTable(run, [
          ['cpu_temp', 'CPU temperature (°C)'],
          ['gpu_temp', 'GPU temperature (°C)'],
        ]),
        sources: src,
        csv,
      },
      {
        id: `${run.id}-throttling`,
        title: 'Clock against temperature',
        takeaway:
          'A clock that falls as temperature climbs is thermal throttling; a flat clock ' +
          'means the platform held its performance for the whole run.',
        spec: {
          kind: 'scatter',
          xName: 'CPU temperature (°C)',
          yName: 'CPU clock (MHz)',
          series: [
            {
              name: run.label,
              colorVar: seriesVarName(run, [run]),
              data: decimate(t.elapsed_sec, 200).map((_, i) => {
                const step = Math.max(1, Math.ceil(t.elapsed_sec.length / 200));
                return [t.metrics.cpu_temp?.[i * step] ?? 0, t.metrics.cpu_freq_mhz?.[i * step] ?? 0];
              }) as unknown as number[][],
            },
          ],
        },
        table: runStatTable(run, [
          ['cpu_temp', 'CPU temperature (°C)'],
          ['cpu_freq_mhz', 'CPU clock (MHz)'],
        ]),
        sources: src,
        csv,
      },
      {
        id: `${run.id}-efficiency`,
        title: 'Compute delivered per watt',
        takeaway:
          'CPU utilization divided by instantaneous board power, showing how efficiency ' +
          'moves as the workload shifts between planning and perception.',
        spec: {
          kind: 'line',
          x: decimate(t.elapsed_sec).map(String),
          xName: 'Elapsed time (s)',
          yName: 'CPU % per watt',
          unit: '',
          digits: 3,
          series: [
            {
              name: 'CPU % / W',
              colorVar: seriesVarName(run, [run]),
              data: decimate(
                (t.metrics.cpu_total ?? []).map((v, i) => {
                  const p = t.metrics[powerMetric]?.[i];
                  return v !== null && p ? Number((v / p).toFixed(4)) : null;
                }),
              ),
            },
          ],
        },
        table: {
          columns: ['Metric', 'Value'],
          rows: [
            ['Mean available compute per watt (GHz-cores/W)', fmt(run.derived.ghz_cores_per_watt, 3)],
            ['Mean GPU utilization per watt (%/W)', fmt(run.derived.gpu_percent_per_watt, 3)],
            ['Mean board power (W)', fmt(run.derived.mean_power_w)],
          ],
        },
        sources: src,
        csv,
      },
    ],
  });

  // -- System behaviour -----------------------------------------------------
  const step = Math.max(1, Math.ceil(t.elapsed_sec.length / 250));
  sections.push({
    id: 'run-system',
    icon: 'chart',
    title: 'System behaviour',
    lede: 'Stability, I/O, and process load, the context around the headline counters.',
    headline: {
      id: `${run.id}-cpu-gpu-correlation`,
      title: 'CPU against GPU utilization',
      takeaway:
        'Each point is one second of the run. A tight cluster means the two resources ' +
        'move together; a wide spread means one is waiting on the other.',
      spec: {
        kind: 'scatter',
        xName: 'CPU utilization (%)',
        yName: 'GPU utilization (%)',
        series: [
          {
            name: run.label,
            colorVar: seriesVarName(run, [run]),
            data: Array.from({ length: Math.floor(t.elapsed_sec.length / step) }, (_, i) => [
              t.metrics.cpu_total?.[i * step] ?? 0,
              t.metrics.gpu_util?.[i * step] ?? 0,
            ]) as unknown as number[][],
          },
        ],
      },
      table: runStatTable(run, [
        ['cpu_total', 'CPU total (%)'],
        ['gpu_util', 'GPU utilization (%)'],
      ]),
      sources: src,
      csv,
    },
    supporting: [
      ...(t.rolling_std
        ? [
            {
              id: `${run.id}-stability`,
              title: 'Rolling stability',
              takeaway: `Standard deviation over a ${t.rolling_std.window}-sample window. Spikes are moments the load became bursty rather than steady.`,
              spec: {
                kind: 'line',
                x: decimate(t.elapsed_sec).map(String),
                xName: 'Elapsed time (s)',
                yName: 'Rolling std. dev. (%)',
                unit: '%',
                digits: 2,
                series: [
                  {
                    name: 'CPU',
                    colorVar: seriesVarName(run, [run]),
                    data: decimate(t.rolling_std.series.cpu_total ?? []),
                  },
                  {
                    name: 'GPU',
                    colorVar: seriesVarName(run, [run]),
                    dashed: true,
                    data: decimate(t.rolling_std.series.gpu_util ?? []),
                  },
                ],
              },
              table: {
                columns: ['Series', 'Window (samples)'],
                rows: [
                  ['CPU total', t.rolling_std.window],
                  ['GPU utilization', t.rolling_std.window],
                ],
              },
              sources: src,
              csv,
            } as ChartDef,
          ]
        : []),
      {
        id: `${run.id}-network`,
        title: 'Network throughput',
        takeaway:
          'Sensor data arriving over the wired DDS link from the simulation machine. Every ' +
          'platform is offered the same load.',
        spec: {
          kind: 'line',
          x: decimate(t.elapsed_sec).map(String),
          xName: 'Elapsed time (s)',
          yName: 'Throughput (MB/s)',
          unit: 'MB/s',
          digits: 1,
          series: [
            {
              name: 'Received',
              colorVar: seriesVarName(run, [run]),
              data: decimate(t.metrics.net_recv_rate_mbps ?? []),
            },
            {
              name: 'Sent',
              colorVar: seriesVarName(run, [run]),
              dashed: true,
              data: decimate(t.metrics.net_sent_rate_mbps ?? []),
            },
          ],
        },
        table: runStatTable(run, [
          ['net_recv_rate_mbps', 'Network received (MB/s)'],
          ['net_sent_rate_mbps', 'Network sent (MB/s)'],
          ['net_errors', 'Network errors'],
        ]),
        sources: src,
        csv,
      },
      {
        id: `${run.id}-disk`,
        title: 'Disk throughput',
        takeaway: 'Disk read and write throughput across the run.',
        spec: {
          kind: 'line',
          x: decimate(t.elapsed_sec).map(String),
          xName: 'Elapsed time (s)',
          yName: 'Throughput (MB/s)',
          unit: 'MB/s',
          digits: 2,
          series: [
            {
              name: 'Read',
              colorVar: seriesVarName(run, [run]),
              data: decimate(t.metrics.disk_read_rate_mbps ?? []),
            },
            {
              name: 'Write',
              colorVar: seriesVarName(run, [run]),
              dashed: true,
              data: decimate(t.metrics.disk_write_rate_mbps ?? []),
            },
          ],
        },
        table: runStatTable(run, [
          ['disk_read_rate_mbps', 'Disk read (MB/s)'],
          ['disk_write_rate_mbps', 'Disk write (MB/s)'],
        ]),
        sources: src,
        csv,
      },
      {
        id: `${run.id}-load`,
        title: 'Load average',
        takeaway:
          'Run-queue depth. A load average well above the core count means threads are ' +
          'waiting for a core rather than running on one.',
        spec: {
          kind: 'line',
          x: decimate(t.elapsed_sec).map(String),
          xName: 'Elapsed time (s)',
          yName: 'Load average',
          unit: '',
          digits: 2,
          series: [
            {
              name: '1 minute',
              colorVar: seriesVarName(run, [run]),
              data: decimate(t.metrics.load_1m ?? []),
            },
            {
              name: '5 minute',
              colorVar: seriesVarName(run, [run]),
              dashed: true,
              data: decimate(t.metrics.load_5m ?? []),
            },
          ],
        },
        table: runStatTable(run, [
          ['load_1m', 'Load average (1m)'],
          ['load_5m', 'Load average (5m)'],
          ['load_15m', 'Load average (15m)'],
        ]),
        sources: src,
        csv,
      },
      {
        id: `${run.id}-processes`,
        title: 'Process count',
        takeaway: 'Total processes on the machine while the benchmark runs.',
        spec: runLine(run, 'process_count', 'Processes', '', 0),
        table: runStatTable(run, [['process_count', 'Process count']]),
        sources: src,
        csv,
      },
    ],
  });

  return sections;
}

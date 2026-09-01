/**
 * Chart runtime.
 *
 * One ECharts instance per `[data-chart]` element on the page. Every chart is
 * described by a serialized spec built at build time; this module resolves the
 * theme's CSS custom properties to concrete colors, builds the ECharts option,
 * and re-themes and resizes on demand.
 *
 * Charts are never the only route to the data: each figure also ships a data
 * table, so nothing here is load-bearing for accessibility.
 */

import * as echarts from 'echarts';

type SeriesSpec = {
  name: string;
  colorVar: string;
  dashed?: boolean;
  data: (number | null)[] | number[][];
  stack?: string;
  faded?: boolean;
  labels?: (string | null)[];
};

type ChartSpec = {
  kind: 'line' | 'bar' | 'stacked' | 'radar' | 'heatmap' | 'scatter' | 'histogram';
  x?: (string | number)[];
  xName?: string;
  yName?: string;
  series: SeriesSpec[];
  indicators?: { name: string; max: number }[];
  unit?: string;
  digits?: number;
  yMax?: number;
  horizontal?: boolean;
  overlap?: boolean;
  noLegend?: boolean;
  heatmap?: { rows: string[]; cols: number[]; max: number };
  scatterLabels?: string[];
};

const RAMP = ['--ramp-0', '--ramp-1', '--ramp-2', '--ramp-3', '--ramp-4', '--ramp-5', '--ramp-6'];

function cssVar(name: string, root: HTMLElement): string {
  return getComputedStyle(root).getPropertyValue(name).trim() || '#888';
}

function palette(root: HTMLElement) {
  return {
    text: cssVar('--text-primary', root),
    secondary: cssVar('--text-secondary', root),
    muted: cssVar('--text-muted', root),
    border: cssVar('--border', root),
    surface: cssVar('--surface-1', root),
    surface2: cssVar('--surface-2', root),
    ramp: RAMP.map((v) => cssVar(v, root)),
  };
}

function withAlpha(hex: string, alpha: number): string {
  const m = /^#?([\da-f]{6})$/i.exec(hex.replace('#', '#'));
  if (!m) return hex;
  const int = parseInt(m[1], 16);
  return `rgba(${(int >> 16) & 255}, ${(int >> 8) & 255}, ${int & 255}, ${alpha})`;
}

function baseOption(p: ReturnType<typeof palette>, spec: ChartSpec) {
  return {
    animation: false,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: p.secondary },
    grid: {
      left: 8,
      right: 20,
      top: spec.series.length > 1 && !spec.noLegend ? 44 : 20,
      bottom: 8,
      containLabel: true,
    },
    legend:
      spec.series.length > 1 && !spec.noLegend
        ? {
            top: 0,
            left: 0,
            itemWidth: 14,
            itemHeight: 3,
            itemGap: 18,
            icon: 'roundRect',
            textStyle: { color: p.secondary, fontSize: 12 },
          }
        : undefined,
    tooltip: {
      backgroundColor: p.surface,
      borderColor: p.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: p.text, fontSize: 12 },
      extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,.14); border-radius: 6px;',
    },
  };
}

function axisCommon(p: ReturnType<typeof palette>) {
  return {
    axisLine: { lineStyle: { color: p.border } },
    axisTick: { show: false },
    axisLabel: { color: p.muted, fontSize: 11 },
    nameTextStyle: { color: p.secondary, fontSize: 11, padding: [0, 0, 0, 0] },
    splitLine: { lineStyle: { color: p.border, type: 'dashed' as const, opacity: 0.7 } },
  };
}

function buildOption(spec: ChartSpec, root: HTMLElement) {
  const p = palette(root);
  const colors = spec.series.map((s) => cssVar(s.colorVar, root));
  const opt: Record<string, unknown> = baseOption(p, spec);
  const ax = axisCommon(p);
  const unit = spec.unit ?? '';
  const digits = spec.digits ?? 1;

  const fmtVal = (v: unknown) =>
    typeof v === 'number' ? `${v.toFixed(digits)}${unit ? ' ' + unit : ''}` : 'n/a';

  if (spec.kind === 'line') {
    opt.tooltip = {
      ...(opt.tooltip as object),
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: p.muted, width: 1 } },
      valueFormatter: fmtVal,
    };
    opt.xAxis = { ...ax, type: 'category', boundaryGap: false, data: spec.x, name: spec.xName, nameLocation: 'middle', nameGap: 28 };
    opt.yAxis = { ...ax, type: 'value', name: spec.yName, nameLocation: 'middle', nameGap: 42, max: spec.yMax };
    opt.series = spec.series.map((s, i) => ({
      type: 'line',
      name: s.name,
      data: s.data,
      showSymbol: false,
      symbol: 'circle',
      symbolSize: 8,
      sampling: 'lttb',
      lineStyle: { width: 2, color: colors[i], type: s.dashed ? 'dashed' : 'solid' },
      itemStyle: { color: colors[i] },
      emphasis: { focus: 'series' },
    }));
    return opt;
  }

  if (spec.kind === 'histogram') {
    opt.tooltip = { ...(opt.tooltip as object), trigger: 'axis', valueFormatter: fmtVal };
    opt.xAxis = { ...ax, type: 'category', data: spec.x, name: spec.xName, nameLocation: 'middle', nameGap: 28 };
    opt.yAxis = { ...ax, type: 'value', name: spec.yName, nameLocation: 'middle', nameGap: 52 };
    opt.series = spec.series.map((s, i) => ({
      type: 'bar',
      name: s.name,
      data: s.data,
      barGap: '10%',
      itemStyle: { color: withAlpha(colors[i], 0.75), borderRadius: [3, 3, 0, 0] },
      emphasis: { focus: 'series', itemStyle: { color: colors[i] } },
    }));
    return opt;
  }

  if (spec.kind === 'bar' || spec.kind === 'stacked') {
    const stacked = spec.kind === 'stacked';
    opt.tooltip = {
      ...(opt.tooltip as object),
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: fmtVal,
    };
    const cat = { ...ax, type: 'category', data: spec.x, splitLine: { show: false } };
    const val = { ...ax, type: 'value', name: spec.yName, nameLocation: 'middle', nameGap: 48, max: spec.yMax };
    if (spec.horizontal) {
      opt.xAxis = { ...val, nameGap: 30 };
      opt.yAxis = { ...cat, inverse: true };
    } else {
      opt.xAxis = cat;
      opt.yAxis = val;
    }
    opt.series = spec.series.map((s, i) => ({
      type: 'bar',
      name: s.name,
      data: s.data,
      stack: stacked ? (s.stack ?? 'total') : undefined,
      // `overlap` charts carry one non-null value per series, so the series
      // share a slot instead of being grouped side by side within it.
      barGap: spec.overlap ? '-100%' : undefined,
      barMaxWidth: 54,
      // 2px surface gap between adjacent/stacked fills
      itemStyle: {
        color: s.faded ? withAlpha(colors[i], 0.22) : colors[i],
        borderColor: p.surface,
        borderWidth: stacked ? 2 : 0,
        borderRadius: stacked ? 0 : spec.horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
      },
      label: s.labels
        ? {
            show: true,
            position: stacked ? 'inside' : spec.horizontal ? 'right' : 'top',
            formatter: (d: { dataIndex: number }) => s.labels?.[d.dataIndex] ?? '',
            color: stacked && !s.faded ? '#fff' : p.text,
            fontSize: 11,
            fontFamily: 'JetBrains Mono, ui-monospace, monospace',
          }
        : undefined,
      emphasis: { focus: 'series' },
    }));
    return opt;
  }

  if (spec.kind === 'radar') {
    opt.tooltip = { ...(opt.tooltip as object), trigger: 'item' };
    opt.radar = {
      indicator: spec.indicators,
      shape: 'polygon',
      radius: '66%',
      center: ['50%', '56%'],
      axisName: { color: p.secondary, fontSize: 11 },
      splitLine: { lineStyle: { color: p.border } },
      splitArea: { areaStyle: { color: [p.surface, p.surface2] } },
      axisLine: { lineStyle: { color: p.border } },
    };
    opt.series = [
      {
        type: 'radar',
        symbolSize: 6,
        data: spec.series.map((s, i) => ({
          name: s.name,
          value: s.data,
          lineStyle: { width: 2, color: colors[i], type: s.dashed ? 'dashed' : 'solid' },
          itemStyle: { color: colors[i] },
          areaStyle: { color: withAlpha(colors[i], 0.16) },
        })),
      },
    ];
    return opt;
  }

  if (spec.kind === 'heatmap' && spec.heatmap) {
    opt.tooltip = {
      ...(opt.tooltip as object),
      trigger: 'item',
      formatter: (d: { value: number[] }) =>
        `Core ${spec.heatmap!.rows[d.value[1]]} @ ${spec.heatmap!.cols[d.value[0]]}s<br/><b>${d.value[2].toFixed(0)}%</b>`,
    };
    opt.legend = undefined;
    opt.grid = { left: 8, right: 20, top: 8, bottom: 52, containLabel: true };
    opt.xAxis = {
      ...ax,
      type: 'category',
      data: spec.heatmap.cols,
      name: spec.xName,
      nameLocation: 'middle',
      nameGap: 28,
      splitLine: { show: false },
      axisLabel: { color: p.muted, fontSize: 11, interval: Math.ceil(spec.heatmap.cols.length / 10) },
    };
    opt.yAxis = {
      ...ax,
      type: 'category',
      data: spec.heatmap.rows,
      name: spec.yName,
      nameLocation: 'middle',
      nameGap: 34,
      splitLine: { show: false },
      axisLabel: { color: p.muted, fontSize: 10, interval: spec.heatmap.rows.length > 20 ? 1 : 0 },
    };
    opt.visualMap = {
      min: 0,
      max: spec.heatmap.max,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 12,
      itemHeight: 120,
      text: [`${spec.heatmap.max}%`, '0%'],
      textStyle: { color: p.muted, fontSize: 11 },
      inRange: { color: p.ramp },
    };
    opt.series = [
      {
        type: 'heatmap',
        data: spec.series[0].data,
        progressive: 4000,
        emphasis: { itemStyle: { borderColor: p.text, borderWidth: 1 } },
      },
    ];
    return opt;
  }

  if (spec.kind === 'scatter') {
    opt.tooltip = {
      ...(opt.tooltip as object),
      trigger: 'item',
      formatter: (d: { seriesName: string; value: number[] }) =>
        `<b>${d.seriesName}</b><br/>${spec.xName}: ${d.value[0].toFixed(1)}<br/>${spec.yName}: ${d.value[1].toFixed(2)}`,
    };
    opt.xAxis = { ...ax, type: 'value', name: spec.xName, nameLocation: 'middle', nameGap: 30, scale: true };
    opt.yAxis = { ...ax, type: 'value', name: spec.yName, nameLocation: 'middle', nameGap: 48, scale: true };
    opt.series = spec.series.map((s, i) => ({
      type: 'scatter',
      name: s.name,
      data: s.data,
      symbolSize: 16,
      itemStyle: { color: colors[i], borderColor: p.surface, borderWidth: 2 },
      label: {
        show: true,
        position: 'right',
        formatter: s.name,
        color: p.text,
        fontSize: 11,
      },
    }));
    return opt;
  }

  return opt;
}

const instances = new Map<HTMLElement, echarts.ECharts>();

function render(el: HTMLElement) {
  const raw = el.getAttribute('data-chart');
  if (!raw) return;
  let spec: ChartSpec;
  try {
    spec = JSON.parse(raw) as ChartSpec;
  } catch {
    return;
  }
  let chart = instances.get(el);
  if (!chart) {
    chart = echarts.init(el, undefined, { renderer: 'canvas' });
    instances.set(el, chart);
  }
  chart.setOption(buildOption(spec, el), { notMerge: true });
  chart.resize();
}

function mount(el: HTMLElement) {
  if (el.dataset.mounted === 'true') return;
  el.dataset.mounted = 'true';
  render(el);

  const ro = new ResizeObserver(() => instances.get(el)?.resize());
  ro.observe(el);
}

function mountAll() {
  const targets = Array.from(document.querySelectorAll<HTMLElement>('[data-chart]'));
  if (!('IntersectionObserver' in window)) {
    targets.forEach(mount);
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          mount(entry.target as HTMLElement);
          io.unobserve(entry.target);
        }
      }
    },
    { rootMargin: '300px' },
  );
  targets.forEach((el) => {
    // A chart inside a closed <details> has no box; mount it when it opens.
    const details = el.closest('details');
    if (details && !details.open) {
      details.addEventListener('toggle', () => details.open && mount(el), { once: true });
    }
    io.observe(el);
  });
}

/** Re-theme every mounted chart when the viewer switches light/dark. */
function watchTheme() {
  const rerender = () => {
    // Let the new custom-property values settle before re-reading them.
    requestAnimationFrame(() => {
      instances.forEach((_, el) => render(el));
    });
  };
  new MutationObserver(rerender).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', rerender);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    mountAll();
    watchTheme();
  });
} else {
  mountAll();
  watchTheme();
}

export {};

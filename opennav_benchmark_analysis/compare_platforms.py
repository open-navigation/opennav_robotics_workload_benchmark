#!/usr/bin/env python3

# Copyright 2026 Open Navigation LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cross-platform benchmark comparison and visualization.

Usage:
    python compare_platforms.py --amd <file> --orin <file> --thor <file> [--output-dir ./output]
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import (
    load_run, compute_stats, save_plot, build_html_report, get_metric_label,
    PLATFORM_LABELS
)

# Vibrant colors matching Plotly's default colorful palette
PLATFORM_COLORS = {
    'amd': '#EF553B',
    'orin': '#00CC96',
    'thor': '#636EFA',
}

PLATFORM_ARG_LABELS = {
    'amd': 'AMD Ryzen AI Max+ 395',
    'orin': 'NVIDIA Jetson Orin',
    'thor': 'NVIDIA Jetson Thor',
}


def plot_timeseries_comparison(platforms, metric, title, ylabel, colors=PLATFORM_COLORS):
    """Overlaid time-series of a single metric across all platforms."""
    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        if metric not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df[metric],
            mode='lines', name=PLATFORM_ARG_LABELS[key],
            line=dict(color=colors[key], width=2),
        ))

    fig.update_layout(
        title=title,
        xaxis_title='Elapsed Time (s)',
        yaxis_title=ylabel,
        template='plotly',
        legend=dict(x=0.01, y=0.99),
    )
    return fig


def plot_cpu_comparison(platforms):
    """Overlaid total CPU % for all platforms."""
    return plot_timeseries_comparison(
        platforms, 'cpu_total',
        'CPU Utilization Comparison', 'CPU Utilization (%)',
    )


def plot_gpu_comparison(platforms):
    """Overlaid GPU utilization % for all platforms."""
    return plot_timeseries_comparison(
        platforms, 'gpu_util',
        'GPU Utilization Comparison', 'GPU Utilization (%)',
    )


def plot_gpu_memory(platforms):
    """GPU memory usage comparison."""
    return plot_timeseries_comparison(
        platforms, 'gpu_mem_used_mb',
        'GPU Memory Usage Comparison', 'GPU Memory Used (MB)',
    )


def plot_power_comparison(platforms):
    """Power draw comparison across platforms."""
    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        # Use whichever power metric is available
        power_col = None
        for col in ['gpu_power_w', 'board_power_w']:
            if col in df.columns:
                power_col = col
                break
        if power_col is None:
            continue
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df[power_col],
            mode='lines', name=PLATFORM_ARG_LABELS[key],
            line=dict(color=PLATFORM_COLORS[key], width=2),
        ))

    fig.update_layout(
        title='Power Draw Comparison',
        xaxis_title='Elapsed Time (s)',
        yaxis_title='Power (W)',
        template='plotly',
        legend=dict(x=0.01, y=0.99),
    )
    return fig


def plot_thermal_comparison(platforms):
    """CPU and GPU temps per platform, overlaid."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=('CPU Temperature', 'GPU Temperature'),
                        vertical_spacing=0.12)

    for key, (meta, df) in platforms.items():
        if 'cpu_temp' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df['cpu_temp'],
                mode='lines', name=f'{PLATFORM_ARG_LABELS[key]} CPU',
                line=dict(color=PLATFORM_COLORS[key], width=2),
            ), row=1, col=1)
        if 'gpu_temp' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df['gpu_temp'],
                mode='lines', name=f'{PLATFORM_ARG_LABELS[key]} GPU',
                line=dict(color=PLATFORM_COLORS[key], width=2, dash='dash'),
            ), row=2, col=1)

    fig.update_yaxes(title_text='Temperature (°C)', row=1, col=1)
    fig.update_yaxes(title_text='Temperature (°C)', row=2, col=1)
    fig.update_xaxes(title_text='Elapsed Time (s)', row=2, col=1)
    fig.update_layout(
        title='Thermal Comparison',
        template='plotly',
        height=600,
    )
    return fig


def plot_memory_bandwidth_comparison(platforms):
    """Memory bus utilization and estimated bandwidth per platform."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=('Memory Bus Utilization', 'Estimated Memory Bandwidth'),
                        vertical_spacing=0.12)

    for key, (meta, df) in platforms.items():
        if 'mem_busy_percent' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df['mem_busy_percent'],
                mode='lines', name=f'{PLATFORM_ARG_LABELS[key]}',
                line=dict(color=PLATFORM_COLORS[key], width=2),
            ), row=1, col=1)
        if 'mem_bandwidth_gbps' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df['mem_bandwidth_gbps'],
                mode='lines', name=f'{PLATFORM_ARG_LABELS[key]}',
                line=dict(color=PLATFORM_COLORS[key], width=2),
                showlegend=False,
            ), row=2, col=1)

    fig.update_yaxes(title_text='Utilization (%)', row=1, col=1)
    fig.update_yaxes(title_text='Bandwidth (GB/s)', row=2, col=1)
    fig.update_xaxes(title_text='Elapsed Time (s)', row=2, col=1)
    fig.update_layout(
        title='Memory Bandwidth Comparison',
        template='plotly',
        height=600,
    )
    return fig


def plot_ram_comparison(platforms):
    """RAM usage comparison."""
    return plot_timeseries_comparison(
        platforms, 'ram_percent',
        'RAM Usage Comparison', 'RAM Usage (%)',
    )


def plot_resource_headroom(platforms):
    """Stacked bar chart: used vs available for CPU, GPU, and VRAM per platform."""
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=('CPU Headroom', 'GPU Headroom', 'VRAM Headroom'),
        horizontal_spacing=0.08,
    )

    def hex_to_rgba(hex_color, alpha):
        """Convert hex color to rgba string."""
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'

    for key, (meta, df) in platforms.items():
        label = PLATFORM_ARG_LABELS[key]
        color = PLATFORM_COLORS[key]
        avail_color = hex_to_rgba(color, 0.25)

        # CPU: used vs available, plus free core equivalents
        if 'cpu_total' in df.columns:
            cpu_used = df['cpu_total'].mean()
            cpu_avail = 100 - cpu_used
            core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
            num_cores = len(core_cols) if core_cols else 1
            free_cores = cpu_avail / 100.0 * num_cores

            fig.add_trace(go.Bar(
                x=[label], y=[cpu_used],
                name=f'{label} Used', marker_color=color,
                text=[f'{cpu_used:.1f}%'], textposition='inside',
                showlegend=False,
            ), row=1, col=1)
            fig.add_trace(go.Bar(
                x=[label], y=[cpu_avail],
                name=f'{label} Available', marker_color=avail_color,
                text=[f'{cpu_avail:.1f}% ({free_cores:.1f} cores free)'],
                textposition='inside',
                showlegend=False,
            ), row=1, col=1)

        # GPU utilization
        if 'gpu_util' in df.columns:
            gpu_used = df['gpu_util'].mean()
            gpu_avail = 100 - gpu_used
            fig.add_trace(go.Bar(
                x=[label], y=[gpu_used],
                marker_color=color,
                text=[f'{gpu_used:.1f}%'], textposition='inside',
                showlegend=False,
            ), row=1, col=2)
            fig.add_trace(go.Bar(
                x=[label], y=[gpu_avail],
                marker_color=avail_color,
                text=[f'{gpu_avail:.1f}% free'], textposition='inside',
                showlegend=False,
            ), row=1, col=2)

        # VRAM
        if 'gpu_mem_used_mb' in df.columns and 'gpu_mem_total_mb' in df.columns:
            vram_used = df['gpu_mem_used_mb'].mean()
            vram_total = df['gpu_mem_total_mb'].mean()
            vram_free = vram_total - vram_used
            fig.add_trace(go.Bar(
                x=[label], y=[vram_used],
                marker_color=color,
                text=[f'{vram_used:.0f} MB'], textposition='inside',
                showlegend=False,
            ), row=1, col=3)
            fig.add_trace(go.Bar(
                x=[label], y=[vram_free],
                marker_color=avail_color,
                text=[f'{vram_free:.0f} MB free'], textposition='inside',
                showlegend=False,
            ), row=1, col=3)

    fig.update_layout(
        barmode='stack',
        title='Resource Headroom — Used (solid) vs Available (faded)',
        template='plotly',
        height=500,
        showlegend=False,
    )
    fig.update_yaxes(title_text='CPU (%)', range=[0, 105], row=1, col=1)
    fig.update_yaxes(title_text='GPU (%)', range=[0, 105], row=1, col=2)
    fig.update_yaxes(title_text='VRAM (MB)', row=1, col=3)
    return fig


def plot_cpu_core_histogram(platforms):
    """Overlaid histograms of per-core CPU utilization across platforms."""
    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
        if not core_cols:
            continue
        # Flatten all per-core samples into one array
        all_core_values = df[core_cols].values.flatten()

        fig.add_trace(go.Histogram(
            x=all_core_values,
            name=PLATFORM_ARG_LABELS[key],
            marker_color=PLATFORM_COLORS[key],
            opacity=0.6,
            xbins=dict(start=0, end=100, size=5),
        ))

    fig.update_layout(
        title='CPU Per-Core Utilization Distribution',
        xaxis_title='Core Utilization (%)',
        yaxis_title='Sample Count',
        barmode='overlay',
        template='plotly',
        legend=dict(x=0.70, y=0.99),
    )
    return fig


def plot_gpu_util_distribution(platforms):
    """Box/violin plots of GPU utilization distribution per platform."""
    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        if 'gpu_util' not in df.columns:
            continue
        fig.add_trace(go.Violin(
            y=df['gpu_util'],
            name=PLATFORM_ARG_LABELS[key],
            marker_color=PLATFORM_COLORS[key],
            box_visible=True,
            meanline_visible=True,
            opacity=0.7,
        ))

    fig.update_layout(
        title='GPU Utilization Distribution',
        yaxis_title='GPU Utilization (%)',
        yaxis=dict(range=[0, 105]),
        template='plotly',
    )
    return fig


def build_efficiency_table(platforms):
    """Build a focused workload efficiency summary table.

    Returns HTML string.
    """
    rows = []
    for key, (meta, df) in platforms.items():
        label = PLATFORM_ARG_LABELS[key]
        row = {'Platform': label}

        # CPU
        if 'cpu_total' in df.columns:
            cpu_mean = df['cpu_total'].mean()
            row['Mean CPU (%)'] = f'{cpu_mean:.1f}'
            row['Available CPU (%)'] = f'{100 - cpu_mean:.1f}'
            core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
            num_cores = len(core_cols) if core_cols else 0
            row['Total Cores'] = str(num_cores)
            free_cores = (100 - cpu_mean) / 100.0 * num_cores
            row['Free Core Equiv.'] = f'{free_cores:.1f}'
        else:
            row['Mean CPU (%)'] = '—'
            row['Available CPU (%)'] = '—'
            row['Total Cores'] = '—'
            row['Free Core Equiv.'] = '—'

        # GPU
        if 'gpu_util' in df.columns:
            gpu_mean = df['gpu_util'].mean()
            row['Mean GPU (%)'] = f'{gpu_mean:.1f}'
            row['Available GPU (%)'] = f'{100 - gpu_mean:.1f}'
        else:
            row['Mean GPU (%)'] = '—'
            row['Available GPU (%)'] = '—'

        # VRAM
        if 'gpu_mem_used_mb' in df.columns and 'gpu_mem_total_mb' in df.columns:
            vram_used = df['gpu_mem_used_mb'].mean()
            vram_total = df['gpu_mem_total_mb'].mean()
            row['VRAM Used (MB)'] = f'{vram_used:.0f}'
            row['VRAM Free (MB)'] = f'{vram_total - vram_used:.0f}'
        else:
            row['VRAM Used (MB)'] = '—'
            row['VRAM Free (MB)'] = '—'

        # RAM
        if 'ram_percent' in df.columns:
            ram_mean = df['ram_percent'].mean()
            row['Mean RAM (%)'] = f'{ram_mean:.1f}'
            row['Available RAM (%)'] = f'{100 - ram_mean:.1f}'
        else:
            row['Mean RAM (%)'] = '—'
            row['Available RAM (%)'] = '—'

        rows.append(row)

    table_df = pd.DataFrame(rows)
    return table_df.to_html(index=False, classes='stats-table')


def plot_summary_bars(platforms):
    """Grouped bar charts comparing mean values of key metrics."""
    key_metrics = [
        'cpu_total', 'gpu_util', 'ram_percent',
        'cpu_temp', 'gpu_temp',
    ]
    # Add power metric (varies by platform)
    power_metrics = ['gpu_power_w', 'board_power_w']
    # Add memory bandwidth if available
    bw_metrics = ['mem_busy_percent', 'mem_bandwidth_gbps']

    # Collect all available metrics across platforms
    all_metrics = set()
    for key, (meta, df) in platforms.items():
        all_metrics.update(df.columns)

    metrics_to_plot = [m for m in key_metrics if m in all_metrics]
    for m in power_metrics:
        if m in all_metrics:
            metrics_to_plot.append(m)
            break
    for m in bw_metrics:
        if m in all_metrics:
            metrics_to_plot.append(m)

    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        means = []
        labels = []
        for m in metrics_to_plot:
            if m in df.columns:
                means.append(df[m].mean())
            else:
                means.append(0)
            labels.append(get_metric_label(m))

        fig.add_trace(go.Bar(
            x=labels, y=means,
            name=PLATFORM_ARG_LABELS[key],
            marker_color=PLATFORM_COLORS[key],
        ))

    fig.update_layout(
        title='Summary Comparison (Mean Values)',
        barmode='group',
        template='plotly',
        yaxis_title='Value',
        height=500,
    )
    return fig


def build_comparison_table(platforms):
    """Build side-by-side stats table for all platforms.

    Returns HTML string.
    """
    # Key metrics to include
    key_metrics = [
        'cpu_total', 'gpu_util',
        'gpu_mem_used_mb', 'ram_percent', 'swap_percent',
        'cpu_temp', 'gpu_temp',
        'gpu_power_w', 'board_power_w',
        'mem_busy_percent', 'mem_bandwidth_gbps',
        'load_1m', 'process_count',
        'disk_read_rate_mbps', 'disk_write_rate_mbps',
        'net_sent_rate_mbps', 'net_recv_rate_mbps',
    ]

    rows = []
    for metric in key_metrics:
        row = {'Metric': get_metric_label(metric)}
        any_data = False
        for key, (meta, df) in platforms.items():
            label = PLATFORM_ARG_LABELS[key]
            if metric in df.columns:
                series = df[metric].dropna()
                if not series.empty:
                    row[f'{label} Mean'] = f'{series.mean():.2f}'
                    row[f'{label} P95'] = f'{series.quantile(0.95):.2f}'
                    row[f'{label} Max'] = f'{series.max():.2f}'
                    any_data = True
                    continue
            row[f'{label} Mean'] = '—'
            row[f'{label} P95'] = '—'
            row[f'{label} Max'] = '—'
        if any_data:
            rows.append(row)

    table_df = pd.DataFrame(rows)
    return table_df.to_html(index=False, classes='stats-table')


def main():
    parser = argparse.ArgumentParser(
        description='Compare benchmark results across 3 hardware platforms.')
    parser.add_argument('--amd', required=True,
                        help='Path to AMD Ryzen AI Max+ metrics JSON')
    parser.add_argument('--orin', required=True,
                        help='Path to Jetson Orin metrics JSON')
    parser.add_argument('--thor', required=True,
                        help='Path to Jetson Thor metrics JSON')
    parser.add_argument('--output-dir', default='./output',
                        help='Output directory (default: ./output)')
    args = parser.parse_args()

    # Load all 3 platforms
    platforms = {}
    for key, path in [('amd', args.amd), ('orin', args.orin), ('thor', args.thor)]:
        if not os.path.isfile(path):
            print(f'Error: file not found: {path}')
            sys.exit(1)
        print(f'Loading {PLATFORM_ARG_LABELS[key]}: {path}')
        meta, df = load_run(path)
        if df.empty:
            print(f'Error: no samples in {path}')
            sys.exit(1)
        platforms[key] = (meta, df)
        print(f'  Samples: {len(df)}, Platform in file: {meta["platform_label"]}')

    output_dir = os.path.join(args.output_dir, 'comparison')
    os.makedirs(output_dir, exist_ok=True)

    # Generate comparison plots
    plot_funcs = [
        ('Resource Headroom', plot_resource_headroom),
        ('CPU Comparison', plot_cpu_comparison),
        ('CPU Core Histogram', plot_cpu_core_histogram),
        ('GPU Comparison', plot_gpu_comparison),
        ('GPU Utilization Distribution', plot_gpu_util_distribution),
        ('GPU Memory', plot_gpu_memory),
        ('Power Comparison', plot_power_comparison),
        ('Thermal Comparison', plot_thermal_comparison),
        ('Memory Bandwidth', plot_memory_bandwidth_comparison),
        ('RAM Comparison', plot_ram_comparison),
        ('Summary Bar Charts', plot_summary_bars),
    ]

    figures = []
    for name, func in plot_funcs:
        print(f'  Generating: {name}')
        fig = func(platforms)
        fig = save_plot(fig, output_dir, name.lower().replace(' ', '_'))
        figures.append((name, fig))

    # Build tables
    efficiency_html = build_efficiency_table(platforms)
    comparison_html = build_comparison_table(platforms)
    combined_tables = (
        '<h3>Workload Efficiency Summary</h3>\n' + efficiency_html +
        '\n<br>\n<h3>Detailed Metrics Comparison</h3>\n' + comparison_html
    )

    # Build HTML report
    report_path = os.path.join(output_dir, 'report.html')
    build_html_report(
        figures, combined_tables,
        'Cross-Platform Benchmark Comparison',
        report_path,
    )

    print(f'\nOutput directory: {output_dir}')
    print(f'HTML report: {report_path}')
    print(f'PNG plots: {len(figures)} generated')


if __name__ == '__main__':
    main()

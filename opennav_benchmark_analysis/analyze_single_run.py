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

"""Single-run benchmark analysis and visualization.

Usage:
    python analyze_single_run.py <path_to_system_metrics.json> [--output-dir ./output]
"""

import argparse
import os
import sys

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import (
    load_run, compute_stats, save_plot, build_html_report, get_metric_label
)


def plot_cpu_overview(df, metadata):
    """Total CPU % with per-core min/max shaded envelope."""
    fig = go.Figure()

    core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
    if core_cols:
        core_min = df[core_cols].min(axis=1)
        core_max = df[core_cols].max(axis=1)

        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=core_max,
            mode='lines', line=dict(width=0),
            showlegend=False, hoverinfo='skip',
        ))
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=core_min,
            mode='lines', line=dict(width=0),
            fill='tonexty', fillcolor='rgba(99, 110, 250, 0.15)',
            name='Per-Core Range',
        ))

    fig.add_trace(go.Scatter(
        x=df['elapsed_sec'], y=df['cpu_total'],
        mode='lines', name='CPU Total',
        line=dict(color='#636EFA', width=2),
    ))

    fig.update_layout(
        title=f"CPU Utilization — {metadata['platform_label']}",
        xaxis_title='Elapsed Time (s)',
        yaxis_title='CPU Utilization (%)',
        yaxis=dict(range=[0, 105]),
        template='plotly',
    )
    return fig


def plot_cpu_core_heatmap(df, metadata):
    """Heatmap of per-core CPU utilization over time."""
    core_cols = sorted(
        [c for c in df.columns if c.startswith('cpu_core_')],
        key=lambda c: int(c.split('_')[-1])
    )
    if not core_cols:
        return None

    core_data = df[core_cols].values.T
    core_labels = [f'Core {i}' for i in range(len(core_cols))]

    fig = go.Figure(data=go.Heatmap(
        z=core_data,
        x=df['elapsed_sec'].values,
        y=core_labels,
        colorscale='YlOrRd',
        colorbar=dict(title='CPU %'),
        zmin=0, zmax=100,
    ))

    fig.update_layout(
        title=f"Per-Core CPU Utilization Heatmap — {metadata['platform_label']}",
        xaxis_title='Elapsed Time (s)',
        yaxis_title='CPU Core',
        template='plotly',
    )
    return fig


def plot_cpu_core_distribution(df, metadata):
    """Box plot showing per-core utilization distribution + active cores over time."""
    core_cols = sorted(
        [c for c in df.columns if c.startswith('cpu_core_')],
        key=lambda c: int(c.split('_')[-1])
    )
    if not core_cols:
        return None

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Per-Core Utilization Distribution', 'Active Cores Over Time'),
        column_widths=[0.5, 0.5],
    )

    for col in core_cols:
        core_num = col.split('_')[-1]
        fig.add_trace(go.Box(
            y=df[col], name=f'Core {core_num}',
            showlegend=False,
        ), row=1, col=1)

    if 'cores_active_percent' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df['cores_active_percent'],
            mode='lines', name='Active Cores %',
            line=dict(color='#EF553B', width=2),
        ), row=1, col=2)
        fig.update_yaxes(title_text='Active Cores (%)', range=[0, 105], row=1, col=2)
        fig.update_xaxes(title_text='Elapsed Time (s)', row=1, col=2)

    fig.update_yaxes(title_text='CPU Utilization (%)', row=1, col=1)
    fig.update_layout(
        title=f"CPU Core Usage Distribution — {metadata['platform_label']}",
        template='plotly',
        height=500,
    )
    return fig


def plot_gpu_utilization(df, metadata):
    """GPU utilization %, VRAM usage, and clock speed as subplots."""
    gpu_metrics = {
        'gpu_util': ('GPU Utilization (%)', '#00CC96'),
        'gpu_mem_used_mb': ('GPU Memory Used (MB)', '#EF553B'),
        'gpu_clock_mhz': ('GPU Clock (MHz)', '#AB63FA'),
    }
    available = {k: v for k, v in gpu_metrics.items() if k in df.columns}
    if not available:
        return None

    n = len(available)
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08)

    for i, (col, (label, color)) in enumerate(available.items(), 1):
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df[col],
            mode='lines', name=label,
            line=dict(color=color, width=2),
        ), row=i, col=1)
        fig.update_yaxes(title_text=label, row=i, col=1)

    fig.update_xaxes(title_text='Elapsed Time (s)', row=n, col=1)
    fig.update_layout(
        title=f"GPU Utilization — {metadata['platform_label']}",
        template='plotly',
        height=250 * n,
    )
    return fig


def plot_ram_usage(df, metadata):
    """RAM usage: percentage and absolute GB on dual y-axes."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    has_data = False

    # Percentage on primary y-axis
    if 'ram_percent' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df['ram_percent'],
            mode='lines', name='RAM Usage (%)',
            line=dict(color='#636EFA', width=2),
        ), secondary_y=False)
        has_data = True

    # Absolute usage on secondary y-axis (prefer GB, fallback to MB)
    if 'ram_used_gb' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df['ram_used_gb'],
            mode='lines', name='RAM Used (GB)',
            line=dict(color='#EF553B', width=2),
        ), secondary_y=True)
        # Show total as a reference line
        if 'ram_total_gb' in df.columns:
            total_gb = df['ram_total_gb'].iloc[0]
            fig.add_hline(
                y=total_gb, secondary_y=True,
                line_dash='dash', line_color='#AB63FA',
                annotation_text=f'Total: {total_gb:.1f} GB',
                annotation_position='top right',
            )
        fig.update_yaxes(title_text='RAM Used (GB)', secondary_y=True)
        has_data = True
    elif 'ram_used_mb' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df['ram_used_mb'],
            mode='lines', name='RAM Used (MB)',
            line=dict(color='#EF553B', width=2),
        ), secondary_y=True)
        if 'ram_total_mb' in df.columns:
            total_mb = df['ram_total_mb'].iloc[0]
            fig.add_hline(
                y=total_mb, secondary_y=True,
                line_dash='dash', line_color='#AB63FA',
                annotation_text=f'Total: {total_mb:.0f} MB',
                annotation_position='top right',
            )
        fig.update_yaxes(title_text='RAM Used (MB)', secondary_y=True)
        has_data = True

    if not has_data:
        return None

    fig.update_xaxes(title_text='Elapsed Time (s)')
    fig.update_yaxes(title_text='RAM Usage (%)', range=[0, 105], secondary_y=False)
    fig.update_layout(
        title=f"RAM Usage — {metadata['platform_label']}",
        template='plotly',
    )
    return fig


def plot_memory_bandwidth(df, metadata):
    """Memory bus utilization and estimated bandwidth."""
    metrics = []
    if 'mem_busy_percent' in df.columns:
        metrics.append(('mem_busy_percent', 'Memory Bus Utilization (%)', '#00CC96'))
    if 'mem_bandwidth_gbps' in df.columns:
        metrics.append(('mem_bandwidth_gbps', 'Memory Bandwidth (GB/s)', '#AB63FA'))

    if not metrics:
        return None

    n = len(metrics)
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08)

    for i, (col, label, color) in enumerate(metrics, 1):
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df[col],
            mode='lines', name=label,
            line=dict(color=color, width=2),
        ), row=i, col=1)
        fig.update_yaxes(title_text=label, row=i, col=1)

    fig.update_xaxes(title_text='Elapsed Time (s)', row=n, col=1)
    fig.update_layout(
        title=f"Memory & Bandwidth — {metadata['platform_label']}",
        template='plotly',
        height=200 * n,
    )
    return fig


def plot_power_thermal(df, metadata):
    """GPU power draw and CPU/GPU temperatures."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    has_data = False

    # Power on primary y-axis
    power_col = 'gpu_power_w' if 'gpu_power_w' in df.columns else 'board_power_w'
    if power_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df[power_col],
            mode='lines', name=get_metric_label(power_col),
            line=dict(color='#EF553B', width=2),
        ), secondary_y=False)
        has_data = True

    # Temperatures on secondary y-axis
    temp_metrics = [
        ('cpu_temp', 'CPU Temp', '#636EFA'),
        ('gpu_temp', 'GPU Temp', '#FFA15A'),
    ]
    for col, name, color in temp_metrics:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df[col],
                mode='lines', name=name,
                line=dict(color=color, width=2),
            ), secondary_y=True)
            has_data = True

    if not has_data:
        return None

    fig.update_xaxes(title_text='Elapsed Time (s)')
    fig.update_yaxes(title_text='Power (W)', secondary_y=False)
    fig.update_yaxes(title_text='Temperature (°C)', secondary_y=True)
    fig.update_layout(
        title=f"Power & Thermal — {metadata['platform_label']}",
        template='plotly',
    )
    return fig


def plot_io_rates(df, metadata):
    """Disk and network I/O rates (MB/s)."""
    io_metrics = [
        ('disk_read_rate_mbps', 'Disk Read', '#636EFA'),
        ('disk_write_rate_mbps', 'Disk Write', '#EF553B'),
        ('net_sent_rate_mbps', 'Net Sent', '#00CC96'),
        ('net_recv_rate_mbps', 'Net Recv', '#FFA15A'),
    ]
    available = [(c, n, clr) for c, n, clr in io_metrics if c in df.columns]
    if not available:
        return None

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=('Disk I/O (MB/s)', 'Network I/O (MB/s)'),
                        vertical_spacing=0.12)

    for col, name, color in available:
        row = 1 if 'disk' in col else 2
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df[col],
            mode='lines', name=name,
            line=dict(color=color, width=2),
        ), row=row, col=1)

    fig.update_yaxes(title_text='MB/s', row=1, col=1)
    fig.update_yaxes(title_text='MB/s', row=2, col=1)
    fig.update_xaxes(title_text='Elapsed Time (s)', row=2, col=1)
    fig.update_layout(
        title=f"I/O Rates — {metadata['platform_label']}",
        template='plotly',
        height=600,
    )
    return fig


def plot_load_processes(df, metadata):
    """Load averages and process count."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    has_data = False
    load_metrics = [
        ('load_1m', '1 min', '#636EFA'),
        ('load_5m', '5 min', '#00CC96'),
        ('load_15m', '15 min', '#FFA15A'),
    ]
    for col, name, color in load_metrics:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df[col],
                mode='lines', name=f'Load {name}',
                line=dict(color=color, width=2),
            ), secondary_y=False)
            has_data = True

    if 'process_count' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['elapsed_sec'], y=df['process_count'],
            mode='lines', name='Process Count',
            line=dict(color='#AB63FA', width=2, dash='dot'),
        ), secondary_y=True)
        has_data = True

    if not has_data:
        return None

    fig.update_xaxes(title_text='Elapsed Time (s)')
    fig.update_yaxes(title_text='Load Average', secondary_y=False)
    fig.update_yaxes(title_text='Process Count', secondary_y=True)
    fig.update_layout(
        title=f"Load & Processes — {metadata['platform_label']}",
        template='plotly',
    )
    return fig


def main():
    parser = argparse.ArgumentParser(
        description='Analyze a single benchmark run and generate visualizations.')
    parser.add_argument('metrics_file', help='Path to system_metrics JSON file')
    parser.add_argument('--output-dir', default='./output',
                        help='Output directory for plots and report (default: ./output)')
    args = parser.parse_args()

    if not os.path.isfile(args.metrics_file):
        print(f'Error: file not found: {args.metrics_file}')
        sys.exit(1)

    print(f'Loading: {args.metrics_file}')
    metadata, df = load_run(args.metrics_file)

    if df.empty:
        print('Error: no samples found in metrics file')
        sys.exit(1)

    print(f'Platform: {metadata["platform_label"]}')
    print(f'Samples: {len(df)} ({metadata["actual_samples"]} recorded)')

    # Derive run ID from parent directory name
    run_id = os.path.basename(os.path.dirname(os.path.abspath(args.metrics_file)))
    output_dir = os.path.join(args.output_dir, run_id)
    os.makedirs(output_dir, exist_ok=True)

    # Generate all plots
    plot_funcs = [
        ('CPU Overview', plot_cpu_overview),
        ('CPU Core Heatmap', plot_cpu_core_heatmap),
        ('CPU Core Distribution', plot_cpu_core_distribution),
        ('GPU Utilization', plot_gpu_utilization),
        ('RAM Usage', plot_ram_usage),
        ('Memory Bandwidth', plot_memory_bandwidth),
        ('Power & Thermal', plot_power_thermal),
        ('IO Rates', plot_io_rates),
        ('Load & Processes', plot_load_processes),
    ]

    figures = []
    for name, func in plot_funcs:
        print(f'  Generating: {name}')
        fig = func(df, metadata)
        if fig is not None:
            fig = save_plot(fig, output_dir, name.lower().replace(' ', '_').replace('&', 'and'))
            figures.append((name, fig))

    # Compute and format statistics table
    stats_df = compute_stats(df)
    stats_html = stats_df.to_html(
        classes='stats-table',
        float_format=lambda x: f'{x:.2f}',
    )

    # Build HTML report
    report_path = os.path.join(output_dir, 'report.html')
    build_html_report(figures, stats_html,
                      f'Benchmark Report — {metadata["platform_label"]} ({run_id})',
                      report_path)

    print(f'\nOutput directory: {output_dir}')
    print(f'HTML report: {report_path}')
    print(f'PNG plots: {len(figures)} generated')


if __name__ == '__main__':
    main()

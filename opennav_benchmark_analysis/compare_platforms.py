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
    count_completed_missions, count_control_loop_misses,
    parse_planner_loop_times, load_vlm_queries, VLM_OUTCOMES, PLATFORM_LABELS
)

# Vibrant colors matching Plotly's default colorful palette
PLATFORM_COLORS = {
    'amd': '#EF553B',
    'orin': '#00CC96',
    'thor': '#636EFA',
}

PLATFORM_ARG_LABELS = {
    'amd': 'AMD Strix Halo',
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


def plot_cpu_frequency_comparison(platforms):
    """Overlaid CPU frequency time-series — shows x86 clock speed advantage."""
    return plot_timeseries_comparison(
        platforms, 'cpu_freq_mhz',
        'CPU Frequency Comparison', 'CPU Frequency (MHz)',
    )


def plot_peak_core_loading(platforms):
    """Worst-case (max) and mean per-core utilization over time per platform."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=(
            'Peak (Hottest) Core Utilization Over Time',
            'Mean Core Utilization Over Time',
        ),
        vertical_spacing=0.12,
    )

    for key, (meta, df) in platforms.items():
        if 'peak_core_util' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df['peak_core_util'],
                mode='lines', name=f'{PLATFORM_ARG_LABELS[key]} Peak',
                line=dict(color=PLATFORM_COLORS[key], width=2),
            ), row=1, col=1)
        if 'mean_core_util' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['elapsed_sec'], y=df['mean_core_util'],
                mode='lines', name=f'{PLATFORM_ARG_LABELS[key]} Mean',
                line=dict(color=PLATFORM_COLORS[key], width=2, dash='dash'),
            ), row=2, col=1)

    fig.update_yaxes(title_text='Core Utilization (%)', range=[0, 105], row=1, col=1)
    fig.update_yaxes(title_text='Core Utilization (%)', range=[0, 105], row=2, col=1)
    fig.update_xaxes(title_text='Elapsed Time (s)', row=2, col=1)
    fig.update_layout(
        title='Peak vs Mean Core Loading — Real-Time Bottleneck Analysis',
        template='plotly',
        height=600,
    )
    return fig


def plot_absolute_compute_headroom(platforms):
    """Absolute available compute in GHz-cores: accounts for both core count and clock speed."""

    def hex_to_rgba(hex_color, alpha):
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'

    fig = go.Figure()

    headroom_values = {}
    for key, (meta, df) in platforms.items():
        label = PLATFORM_ARG_LABELS[key]
        color = PLATFORM_COLORS[key]
        avail_color = hex_to_rgba(color, 0.25)

        core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
        num_cores = len(core_cols) if core_cols else 1
        cpu_mean = df['cpu_total'].mean() if 'cpu_total' in df.columns else 0
        freq_ghz = df['cpu_freq_ghz'].mean() if 'cpu_freq_ghz' in df.columns else 1.0

        total_ghz_cores = num_cores * freq_ghz
        used_ghz_cores = (cpu_mean / 100.0) * total_ghz_cores
        avail_ghz_cores = total_ghz_cores - used_ghz_cores
        headroom_values[key] = avail_ghz_cores

        fig.add_trace(go.Bar(
            x=[label], y=[used_ghz_cores],
            marker_color=color,
            text=[f'{used_ghz_cores:.1f} GHz-cores'],
            textposition='inside',
            name='Workload Used',
            showlegend=(key == list(platforms.keys())[0]),
            legendgroup='used',
        ))
        fig.add_trace(go.Bar(
            x=[label], y=[avail_ghz_cores],
            marker_color=avail_color,
            text=[f'{avail_ghz_cores:.1f} GHz-cores free'],
            textposition='inside',
            name='Available for Other Tasks',
            showlegend=(key == list(platforms.keys())[0]),
            legendgroup='available',
        ))

    # Add multiplier annotations comparing to the platform with least headroom
    if len(headroom_values) >= 2:
        min_val = min(headroom_values.values())
        if min_val > 0:
            annotations = []
            for key, val in headroom_values.items():
                if val > min_val:
                    multiplier = val / min_val
                    annotations.append(dict(
                        x=PLATFORM_ARG_LABELS[key],
                        y=sum(v for k, (m, d) in platforms.items()
                              if k == key
                              for v in [len([c for c in d.columns if c.startswith('cpu_core_')]) *
                                        (d['cpu_freq_ghz'].mean() if 'cpu_freq_ghz' in d.columns else 1.0)]),
                        text=f'{multiplier:.1f}x more headroom',
                        showarrow=False,
                        yshift=15,
                        font=dict(size=12, color='#333'),
                    ))
            fig.update_layout(annotations=annotations)

    fig.update_layout(
        barmode='stack',
        title='Absolute Compute Headroom (GHz-cores) — Clock Speed x Free Cores',
        template='plotly',
        yaxis_title='GHz-cores',
        height=500,
    )
    return fig


def plot_core_utilization_percentiles(platforms):
    """Grouped bar chart of per-core utilization percentiles (p50, p95, p99) per platform."""
    percentiles = [('p50', 0.50), ('p95', 0.95), ('p99', 0.99)]

    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
        if not core_cols:
            continue
        all_core_values = df[core_cols].values.flatten()

        pct_values = []
        pct_labels = []
        for label, q in percentiles:
            val = np.percentile(all_core_values, q * 100)
            pct_values.append(val)
            pct_labels.append(label)

        fig.add_trace(go.Bar(
            x=pct_labels, y=pct_values,
            name=PLATFORM_ARG_LABELS[key],
            marker_color=PLATFORM_COLORS[key],
            text=[f'{v:.1f}%' for v in pct_values],
            textposition='outside',
        ))

    fig.update_layout(
        title='Per-Core Utilization Percentiles — How Close to Saturation?',
        barmode='group',
        template='plotly',
        yaxis_title='Core Utilization (%)',
        yaxis=dict(range=[0, 105]),
        height=500,
    )
    return fig


def plot_gpu_clock_comparison(platforms):
    """Overlaid GPU clock speed time-series."""
    return plot_timeseries_comparison(
        platforms, 'gpu_clock_mhz',
        'GPU Clock Speed Comparison', 'GPU Clock (MHz)',
    )


def plot_gpu_memory_headroom(platforms):
    """GPU/VRAM memory headroom with system memory context for unified architectures."""

    def hex_to_rgba(hex_color, alpha):
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('GPU/VRAM Memory', 'System RAM Available to GPU'),
        horizontal_spacing=0.10,
    )

    for key, (meta, df) in platforms.items():
        label = PLATFORM_ARG_LABELS[key]
        color = PLATFORM_COLORS[key]
        avail_color = hex_to_rgba(color, 0.25)

        # VRAM
        if 'gpu_mem_used_mb' in df.columns and 'gpu_mem_total_mb' in df.columns:
            vram_used = df['gpu_mem_used_mb'].mean()
            vram_total = df['gpu_mem_total_mb'].mean()
            vram_free = vram_total - vram_used
            vram_pct = vram_used / vram_total * 100 if vram_total > 0 else 0
            fig.add_trace(go.Bar(
                x=[label], y=[vram_used / 1024],
                marker_color=color,
                text=[f'{vram_used / 1024:.1f} GB ({vram_pct:.0f}%)'],
                textposition='inside',
                showlegend=False,
            ), row=1, col=1)
            fig.add_trace(go.Bar(
                x=[label], y=[vram_free / 1024],
                marker_color=avail_color,
                text=[f'{vram_free / 1024:.1f} GB free'],
                textposition='inside',
                showlegend=False,
            ), row=1, col=1)

        # System RAM (relevant for unified memory — AMD can use full system RAM for GPU)
        if 'ram_used_mb' in df.columns and 'ram_total_mb' in df.columns:
            ram_total = df['ram_total_mb'].mean()
            ram_used = df['ram_used_mb'].mean()
            ram_free = ram_total - ram_used
        elif 'ram_percent' in df.columns:
            # Estimate from percentage (no absolute values in older logs)
            ram_pct = df['ram_percent'].mean()
            ram_total = 0
            ram_used = 0
            ram_free = 0
        else:
            continue

        if ram_total > 0:
            fig.add_trace(go.Bar(
                x=[label], y=[ram_used / 1024],
                marker_color=color,
                text=[f'{ram_used / 1024:.1f} GB used'],
                textposition='inside',
                showlegend=False,
            ), row=1, col=2)
            fig.add_trace(go.Bar(
                x=[label], y=[ram_free / 1024],
                marker_color=avail_color,
                text=[f'{ram_free / 1024:.1f} GB free'],
                textposition='inside',
                showlegend=False,
            ), row=1, col=2)

    fig.update_layout(
        barmode='stack',
        title='GPU Memory Headroom — VRAM + System RAM (Unified Memory Advantage)',
        template='plotly',
        height=500,
        showlegend=False,
    )
    fig.update_yaxes(title_text='Memory (GB)', row=1, col=1)
    fig.update_yaxes(title_text='Memory (GB)', row=1, col=2)
    return fig


def plot_performance_per_watt(platforms):
    """Efficiency metrics: available GHz-cores per watt and GPU utilization per watt."""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            'Available Compute Per Watt (GHz-cores/W)',
            'GPU Utilization Per Watt (%/W)',
        ),
        horizontal_spacing=0.10,
    )

    for key, (meta, df) in platforms.items():
        label = PLATFORM_ARG_LABELS[key]
        color = PLATFORM_COLORS[key]

        # Get power draw
        power_col = None
        for col in ['gpu_power_w', 'board_power_w']:
            if col in df.columns:
                power_col = col
                break
        if power_col is None:
            continue
        mean_power = df[power_col].mean()
        if mean_power <= 0:
            continue

        # Available GHz-cores per watt
        core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
        num_cores = len(core_cols) if core_cols else 1
        cpu_mean = df['cpu_total'].mean() if 'cpu_total' in df.columns else 0
        freq_ghz = df['cpu_freq_ghz'].mean() if 'cpu_freq_ghz' in df.columns else 1.0
        avail_ghz_cores = (1 - cpu_mean / 100) * num_cores * freq_ghz
        ghz_per_watt = avail_ghz_cores / mean_power

        fig.add_trace(go.Bar(
            x=[label], y=[ghz_per_watt],
            marker_color=color,
            text=[f'{ghz_per_watt:.2f}'],
            textposition='outside',
            showlegend=False,
        ), row=1, col=1)

        # GPU utilization per watt
        if 'gpu_util' in df.columns:
            gpu_mean = df['gpu_util'].mean()
            gpu_per_watt = gpu_mean / mean_power
            fig.add_trace(go.Bar(
                x=[label], y=[gpu_per_watt],
                marker_color=color,
                text=[f'{gpu_per_watt:.2f}'],
                textposition='outside',
                showlegend=False,
            ), row=1, col=2)

    fig.update_layout(
        title='Performance Per Watt — Efficiency Comparison',
        template='plotly',
        height=500,
        showlegend=False,
    )
    fig.update_yaxes(title_text='GHz-cores / W', row=1, col=1)
    fig.update_yaxes(title_text='GPU % / W', row=1, col=2)
    return fig


def plot_platform_balance_radar(platforms):
    """Radar/spider chart showing overall platform balance across key dimensions."""
    # Define dimensions and how to compute normalized 0-1 scores (higher = better)
    dimensions = [
        'CPU Headroom',
        'GPU Capability',
        'Memory Headroom',
        'Clock Speed',
    ]

    fig = go.Figure()

    # First pass: compute raw values for normalization
    raw_values = {}
    for key, (meta, df) in platforms.items():
        vals = {}
        # CPU Headroom: 100 - cpu_total (higher = more room)
        vals['CPU Headroom'] = 100 - df['cpu_total'].mean() if 'cpu_total' in df.columns else 0

        # GPU Capability: gpu_util mean (shows it's handling the workload)
        vals['GPU Capability'] = df['gpu_util'].mean() if 'gpu_util' in df.columns else 0

        # Memory Headroom: % free (discrete VRAM on AMD, unified RAM on Jetsons)
        if 'gpu_mem_used_mb' in df.columns and 'gpu_mem_total_mb' in df.columns:
            mem_total = df['gpu_mem_total_mb'].mean()
            mem_used = df['gpu_mem_used_mb'].mean()
            vals['Memory Headroom'] = ((mem_total - mem_used) / mem_total * 100) if mem_total > 0 else 0
        elif 'ram_used_mb' in df.columns and 'ram_total_mb' in df.columns:
            mem_total = df['ram_total_mb'].mean()
            mem_used = df['ram_used_mb'].mean()
            vals['Memory Headroom'] = ((mem_total - mem_used) / mem_total * 100) if mem_total > 0 else 0
        else:
            vals['Memory Headroom'] = 0

        # Clock Speed: mean freq in GHz
        vals['Clock Speed'] = df['cpu_freq_ghz'].mean() if 'cpu_freq_ghz' in df.columns else 0

        raw_values[key] = vals

    # Normalize each dimension to 0-1 across platforms
    for key, vals in raw_values.items():
        normalized = []
        for dim in dimensions:
            all_vals = [raw_values[k][dim] for k in raw_values]
            max_val = max(all_vals) if max(all_vals) > 0 else 1
            normalized.append(vals[dim] / max_val)

        fig.add_trace(go.Scatterpolar(
            r=normalized + [normalized[0]],  # close the polygon
            theta=dimensions + [dimensions[0]],
            fill='toself',
            name=PLATFORM_ARG_LABELS[key],
            line=dict(color=PLATFORM_COLORS[key], width=2),
            opacity=0.6,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1.1]),
        ),
        title='Platform Balance — Overall Capability Comparison',
        template='plotly',
        height=600,
    )
    return fig


def plot_single_thread_headroom(platforms):
    """Available single-thread performance headroom per platform."""
    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        label = PLATFORM_ARG_LABELS[key]
        color = PLATFORM_COLORS[key]

        core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
        if not core_cols or 'cpu_freq_ghz' not in df.columns:
            continue

        # Least-loaded core per sample = best candidate for a new RT thread
        min_core_util = df[core_cols].min(axis=1)
        median_min_util = min_core_util.median()
        mean_freq = df['cpu_freq_ghz'].mean()

        # Available single-thread GHz on the least-loaded core
        avail_ghz = (100 - median_min_util) / 100.0 * mean_freq

        fig.add_trace(go.Bar(
            x=[label], y=[avail_ghz],
            marker_color=color,
            text=[f'{avail_ghz:.2f} GHz\n(best core: {median_min_util:.0f}% @ {mean_freq:.1f} GHz)'],
            textposition='outside',
            showlegend=False,
        ))

    fig.update_layout(
        title='Single-Thread Headroom — Can You Run Real-Time Control?',
        yaxis_title='Available Single-Thread Performance (GHz)',
        template='plotly',
        height=500,
        showlegend=False,
    )
    return fig


def plot_gpu_effective_throughput(platforms):
    """GPU effective throughput: utilization * clock speed, showing actual GPU work."""
    return plot_timeseries_comparison(
        platforms, 'gpu_effective_throughput',
        'GPU Effective Throughput — Utilization x Clock Speed',
        'Effective Throughput (GHz)',
    )


def plot_realtime_stability(platforms):
    """Per-core utilization variability — lower = more predictable for real-time."""
    categories = ['Std Dev (%)', 'Coeff. of Variation']

    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
        if not core_cols:
            continue
        all_core_values = df[core_cols].values.flatten()
        std = np.std(all_core_values)
        mean = np.mean(all_core_values)
        cv = (std / mean * 100) if mean > 0 else 0

        fig.add_trace(go.Bar(
            x=categories,
            y=[std, cv],
            name=PLATFORM_ARG_LABELS[key],
            marker_color=PLATFORM_COLORS[key],
            text=[f'{std:.1f}', f'{cv:.1f}%'],
            textposition='outside',
        ))

    fig.update_layout(
        title='Real-Time Stability — Per-Core Utilization Variability (Lower = Better)',
        barmode='group',
        template='plotly',
        yaxis_title='Value',
        height=500,
    )
    return fig


def plot_thermal_runway(platforms):
    """Thermal margin to throttle point (100°C) for CPU and GPU."""
    categories = ['CPU Thermal Margin', 'GPU Thermal Margin']
    T_THROTTLE = 100.0

    fig = go.Figure()

    for key, (meta, df) in platforms.items():
        cpu_margin = T_THROTTLE - df['cpu_temp'].mean() if 'cpu_temp' in df.columns else 0
        gpu_margin = T_THROTTLE - df['gpu_temp'].mean() if 'gpu_temp' in df.columns else 0

        fig.add_trace(go.Bar(
            x=categories,
            y=[cpu_margin, gpu_margin],
            name=PLATFORM_ARG_LABELS[key],
            marker_color=PLATFORM_COLORS[key],
            text=[f'{cpu_margin:.1f}°C', f'{gpu_margin:.1f}°C'],
            textposition='outside',
        ))

    fig.update_layout(
        title='Thermal Runway — Margin to Throttle Point (100°C)',
        barmode='group',
        template='plotly',
        yaxis_title='Margin (°C)',
        height=500,
    )
    return fig


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


def plot_completed_missions(mission_counts):
    """Bar chart of completed missions per platform."""
    fig = go.Figure()

    for key, count in mission_counts.items():
        fig.add_trace(go.Bar(
            x=[PLATFORM_ARG_LABELS[key]],
            y=[count],
            marker_color=PLATFORM_COLORS[key],
            text=[str(count)],
            textposition='outside',
            showlegend=False,
        ))

    fig.update_layout(
        title='Completed Missions (15 Min Window) — Higher Is Better',
        yaxis_title='Missions Completed',
        template='plotly',
        height=500,
    )
    return fig


def plot_planner_cycle_times(platforms_planner):
    """Box plot of planner cycle time distributions per platform."""
    fig = go.Figure()

    for key, data in platforms_planner.items():
        times_ms = [t * 1000 for t in data['times_sec']]
        fig.add_trace(go.Box(
            y=times_ms,
            name=PLATFORM_ARG_LABELS[key],
            marker_color=PLATFORM_COLORS[key],
            boxmean=True,
        ))

    fig.update_layout(
        title='Planner Cycle Time Distribution — Lower Is Better',
        yaxis_title='Cycle Time (ms)',
        template='plotly',
        height=500,
    )
    return fig


def plot_control_loop_misses(miss_counts):
    """Bar chart of control loop rate misses per platform."""
    fig = go.Figure()

    for key, count in miss_counts.items():
        fig.add_trace(go.Bar(
            x=[PLATFORM_ARG_LABELS[key]],
            y=[count],
            marker_color=PLATFORM_COLORS[key],
            text=[str(count)],
            textposition='outside',
            showlegend=False,
        ))

    fig.update_layout(
        title='Control Loop Misses (30 Hz Target) — Lower Is Better',
        yaxis_title='Number of Misses',
        template='plotly',
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


OUTCOME_COLORS = {
    'success': '#00CC96',
    'error': '#EF553B',
    'cancelled': '#FFA15A',
    'retries_exhausted': '#AB63FA',
    'no_image': '#B6E880',
    'stale_image': '#FF97FF',
    'encode_failed': '#FECB52',
}


def plot_vlm_comparison(platforms_vlm):
    """Grouped bar chart of VLM query outcomes per platform."""
    fig = go.Figure()

    platform_names = [PLATFORM_ARG_LABELS[k] for k in platforms_vlm]
    for outcome in VLM_OUTCOMES:
        counts = [platforms_vlm[k]['summary'][outcome] for k in platforms_vlm]
        if any(c > 0 for c in counts):
            fig.add_trace(go.Bar(
                name=outcome,
                x=platform_names,
                y=counts,
                marker_color=OUTCOME_COLORS.get(outcome, '#636EFA'),
            ))

    fig.update_layout(
        title='VLM Query Outcomes',
        xaxis_title='Platform',
        yaxis_title='Query Count',
        barmode='group',
        template='plotly',
        legend=dict(x=0.01, y=0.99),
    )
    return fig


def main():
    parser = argparse.ArgumentParser(
        description='Compare benchmark results across 3 hardware platforms.')
    parser.add_argument('--amd', required=True,
                        help='Path to AMD Strix Halo metrics JSON')
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

    # Count completed missions and control loop misses from ROS logs
    mission_counts = {}
    miss_counts = {}
    for key, path in [('amd', args.amd), ('orin', args.orin), ('thor', args.thor)]:
        mission_counts[key] = count_completed_missions(path)
        miss_counts[key] = count_control_loop_misses(path)

    output_dir = os.path.join(args.output_dir, 'comparison')
    os.makedirs(output_dir, exist_ok=True)

    # Generate comparison plots
    plot_funcs = [
        ('Platform Balance Radar', plot_platform_balance_radar),
        ('Resource Headroom', plot_resource_headroom),
        ('Absolute Compute Headroom', plot_absolute_compute_headroom),
        ('Single-Thread Headroom', plot_single_thread_headroom),
        ('CPU Comparison', plot_cpu_comparison),
        ('CPU Frequency', plot_cpu_frequency_comparison),
        ('Peak Core Loading', plot_peak_core_loading),
        ('CPU Core Histogram', plot_cpu_core_histogram),
        ('Core Utilization Percentiles', plot_core_utilization_percentiles),
        ('GPU Comparison', plot_gpu_comparison),
        ('GPU Clock Speed', plot_gpu_clock_comparison),
        ('GPU Effective Throughput', plot_gpu_effective_throughput),
        ('GPU Utilization Distribution', plot_gpu_util_distribution),
        ('GPU Memory', plot_gpu_memory),
        ('GPU Memory Headroom', plot_gpu_memory_headroom),
        ('Performance Per Watt', plot_performance_per_watt),
        ('Power Comparison', plot_power_comparison),
        ('Thermal Comparison', plot_thermal_comparison),
        ('Thermal Runway', plot_thermal_runway),
        ('RAM Comparison', plot_ram_comparison),
        ('Summary Bar Charts', plot_summary_bars),
    ]

    figures = []
    for name, func in plot_funcs:
        print(f'  Generating: {name}')
        fig = func(platforms)
        fig = save_plot(fig, output_dir, name.lower().replace(' ', '_'))
        figures.append((name, fig))

    # Completed missions chart
    print('  Generating: Completed Missions')
    fig = plot_completed_missions(mission_counts)
    fig = save_plot(fig, output_dir, 'completed_missions')
    figures.append(('Completed Missions', fig))

    # Planner cycle time chart (if planner loop warnings exist)
    platforms_planner = {}
    for key, path in [('amd', args.amd), ('orin', args.orin), ('thor', args.thor)]:
        planner_data = parse_planner_loop_times(path)
        if planner_data:
            platforms_planner[key] = planner_data
    if platforms_planner:
        print('  Generating: Planner Cycle Times')
        fig = plot_planner_cycle_times(platforms_planner)
        fig = save_plot(fig, output_dir, 'planner_cycle_times')
        figures.append(('Planner Cycle Times', fig))

    # Control loop misses chart (different signature — uses miss_counts)
    print('  Generating: Control Loop Misses')
    fig = plot_control_loop_misses(miss_counts)
    fig = save_plot(fig, output_dir, 'control_loop_misses')
    figures.append(('Control Loop Misses', fig))

    # VLM query outcomes chart (if VLM logs exist)
    platforms_vlm = {}
    for key, path in [('amd', args.amd), ('orin', args.orin), ('thor', args.thor)]:
        vlm_data = load_vlm_queries(path)
        if vlm_data:
            platforms_vlm[key] = vlm_data
    if platforms_vlm:
        print('  Generating: VLM Query Outcomes')
        fig = plot_vlm_comparison(platforms_vlm)
        fig = save_plot(fig, output_dir, 'vlm_query_outcomes')
        figures.append(('VLM Query Outcomes', fig))

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

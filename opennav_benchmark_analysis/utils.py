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

"""Shared utilities for benchmark analysis: data loading, statistics, and plotting."""

import glob
import json
import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


# Metrics that are cumulative counters (need delta/rate computation)
CUMULATIVE_METRICS = ['disk_read_mb', 'disk_write_mb', 'net_sent_mb', 'net_recv_mb']

# Friendly display names for metrics
METRIC_LABELS = {
    'cpu_total': 'CPU Total (%)',
    'cpu_freq_mhz': 'CPU Frequency (MHz)',
    'cpu_freq_ghz': 'CPU Frequency (GHz)',
    'peak_core_util': 'Peak Core Utilization (%)',
    'mean_core_util': 'Mean Core Utilization (%)',
    'ram_percent': 'RAM Usage (%)',
    'ram_used_mb': 'RAM Used (MB)',
    'ram_total_mb': 'RAM Total (MB)',
    'ram_used_gb': 'RAM Used (GB)',
    'ram_total_gb': 'RAM Total (GB)',
    'swap_percent': 'Swap Usage (%)',
    'disk_percent': 'Disk Usage (%)',
    'disk_read_rate_mbps': 'Disk Read (MB/s)',
    'disk_write_rate_mbps': 'Disk Write (MB/s)',
    'net_sent_rate_mbps': 'Net Sent (MB/s)',
    'net_recv_rate_mbps': 'Net Recv (MB/s)',
    'net_errors': 'Network Errors',
    'load_1m': 'Load Average (1m)',
    'load_5m': 'Load Average (5m)',
    'load_15m': 'Load Average (15m)',
    'process_count': 'Process Count',
    'cpu_temp': 'CPU Temperature (°C)',
    'gpu_util': 'GPU Utilization (%)',
    'gpu_mem_used_mb': 'GPU Memory Used (MB)',
    'gpu_mem_total_mb': 'GPU Memory Total (MB)',
    'gpu_clock_mhz': 'GPU Clock (MHz)',
    'gpu_mem_clock_mhz': 'GPU Memory Clock (MHz)',
    'gpu_temp': 'GPU Temperature (°C)',
    'gpu_power_w': 'GPU Power (W)',
    'vcn_util': 'VCN Utilization (%)',
    'board_power_w': 'Board Power (W)',
    'emc_freq_mhz': 'EMC Frequency (MHz)',
    'mem_busy_percent': 'Memory Bus Utilization (%)',
    'mem_bandwidth_gbps': 'Memory Bandwidth (GB/s)',
    'gpu_effective_throughput': 'GPU Effective Throughput (GHz)',
    'npu_util': 'NPU Utilization (%)',
    'cores_active_percent': 'Active Cores (%)',
}

# Platform display names
PLATFORM_LABELS = {
    'amd_strix_halo': 'AMD Strix Halo',
    'jetson_orin': 'NVIDIA Jetson Orin',
    'jetson_thor': 'NVIDIA Jetson Thor',
}


def load_run(filepath):
    """Load a benchmark JSON file and return metadata dict and pandas DataFrame.

    Returns:
        tuple: (metadata_dict, DataFrame) where metadata contains platform, start_time,
               duration_sec, actual_samples; DataFrame has elapsed_sec index and all
               metrics including computed rate columns.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    metadata = {
        'platform': data['platform'],
        'platform_label': PLATFORM_LABELS.get(data['platform'], data['platform']),
        'start_time': data.get('start_time'),
        'end_time': data.get('end_time'),
        'duration_sec': data.get('duration_sec'),
        'actual_samples': data.get('actual_samples', len(data['samples'])),
        'filepath': filepath,
    }

    samples = data['samples']
    if not samples:
        return metadata, pd.DataFrame()

    # Expand cpu_cores array into individual columns
    rows = []
    for s in samples:
        row = {k: v for k, v in s.items() if k != 'cpu_cores'}
        cores = s.get('cpu_cores', [])
        for i, val in enumerate(cores):
            row[f'cpu_core_{i}'] = val
        row['num_cores'] = len(cores)
        rows.append(row)

    df = pd.DataFrame(rows)

    # Compute elapsed time from first sample
    if 'timestamp' in df.columns:
        df['elapsed_sec'] = df['timestamp'] - df['timestamp'].iloc[0]

    # Compute rates from cumulative counters (MB/s)
    for col in CUMULATIVE_METRICS:
        if col in df.columns:
            rate_col = col.replace('_mb', '_rate_mbps')
            df[rate_col] = df[col].diff().clip(lower=0)
            # First value is NaN from diff, fill with 0
            df[rate_col] = df[rate_col].fillna(0)

    # Compute GB columns from MB if present
    for mb_col, gb_col in [('ram_used_mb', 'ram_used_gb'), ('ram_total_mb', 'ram_total_gb')]:
        if mb_col in df.columns:
            df[gb_col] = (df[mb_col] / 1024).round(2)

    # CPU frequency in GHz
    if 'cpu_freq_mhz' in df.columns:
        df['cpu_freq_ghz'] = (df['cpu_freq_mhz'] / 1000).round(3)

    # GPU effective throughput (utilization * clock speed)
    if 'gpu_util' in df.columns and 'gpu_clock_mhz' in df.columns:
        df['gpu_effective_throughput'] = (df['gpu_util'] * df['gpu_clock_mhz'] / 1000).round(2)

    # Per-core derived metrics
    core_cols = [c for c in df.columns if c.startswith('cpu_core_')]
    if core_cols:
        df['peak_core_util'] = df[core_cols].max(axis=1)
        df['mean_core_util'] = df[core_cols].mean(axis=1).round(1)
        active = (df[core_cols] > 5.0).sum(axis=1)
        df['cores_active_percent'] = (active / len(core_cols) * 100).round(1)

    return metadata, df


def compute_stats(df, columns=None):
    """Compute summary statistics for specified columns (or all numeric columns).

    Returns:
        DataFrame with rows=metrics, columns=[mean, std, min, max, p50, p95, p99].
    """
    if columns is None:
        # Exclude internal/index columns
        exclude = {'timestamp', 'elapsed_sec', 'num_cores'}
        columns = [c for c in df.select_dtypes(include='number').columns
                    if c not in exclude]

    stats = {}
    for col in columns:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if series.empty:
            continue
        stats[col] = {
            'mean': round(series.mean(), 2),
            'std': round(series.std(), 2),
            'min': round(series.min(), 2),
            'max': round(series.max(), 2),
            'p50': round(series.quantile(0.50), 2),
            'p95': round(series.quantile(0.95), 2),
            'p99': round(series.quantile(0.99), 2),
        }

    stats_df = pd.DataFrame(stats).T
    stats_df.index.name = 'metric'
    # Add friendly names
    stats_df['label'] = stats_df.index.map(
        lambda x: METRIC_LABELS.get(x, x))
    return stats_df


def save_plot(fig, output_dir, name, width=1200, height=600):
    """Save a Plotly figure as both PNG and return it for HTML embedding.

    Args:
        fig: Plotly Figure object
        output_dir: Directory to save PNG files
        name: Base filename (without extension)
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        The figure object (for HTML embedding)
    """
    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, f'{name}.png')
    try:
        pio.write_image(fig, png_path, width=width, height=height, scale=2)
    except Exception as e:
        print(f'Warning: could not write PNG {png_path}: {e}')
    return fig


def build_html_report(figures, stats_html, title, output_path):
    """Build a self-contained HTML report with all plots and a stats table.

    Args:
        figures: List of (name, Plotly Figure) tuples
        stats_html: HTML string for the statistics table
        title: Report title
        output_path: Path to write the HTML file
    """
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    plot_divs = []
    for i, (name, fig) in enumerate(figures):
        # Embed Plotly.js inline with the first plot; subsequent plots reuse it
        include_js = True if i == 0 else False
        div = pio.to_html(fig, full_html=False, include_plotlyjs=include_js)
        plot_divs.append(f'<div class="plot-section"><h2>{name}</h2>{div}</div>')

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
            color: #333;
        }}
        h1 {{
            border-bottom: 2px solid #2196F3;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #1976D2;
            margin-top: 30px;
        }}
        .plot-section {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: right;
        }}
        th {{
            background: #2196F3;
            color: white;
            text-align: center;
        }}
        td:first-child, th:first-child {{
            text-align: left;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        .metadata {{
            background: #e3f2fd;
            padding: 10px 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {''.join(plot_divs)}
    <div class="plot-section">
        <h2>Summary Statistics</h2>
        {stats_html}
    </div>
</body>
</html>"""

    with open(output_path, 'w') as f:
        f.write(html)
    print(f'HTML report written to: {output_path}')


def get_metric_label(metric):
    """Get a human-readable label for a metric name."""
    return METRIC_LABELS.get(metric, metric)


# Valid VLM query outcome values
VLM_OUTCOMES = [
    'success', 'error', 'cancelled', 'retries_exhausted',
    'no_image', 'stale_image', 'encode_failed',
]


def load_vlm_queries(metrics_filepath):
    """Parse VLM_QUERY lines from vlm_node ROS logs.

    Searches for VLM_QUERY log lines in the ros/ directory sibling to the
    given system_metrics.json file. Each line has the format:
        VLM_QUERY|<action_type>|<outcome>|<duration_sec>|<attempts>|<error>

    Args:
        metrics_filepath: Path to system_metrics.json file.

    Returns:
        dict with 'queries' (list of dicts) and 'summary' (outcome counts
        and duration stats), or None if no VLM logs found.
    """
    run_dir = os.path.dirname(os.path.abspath(metrics_filepath))
    ros_dir = os.path.join(run_dir, 'ros')
    if not os.path.isdir(ros_dir):
        return None

    log_files = glob.glob(os.path.join(ros_dir, 'python3_*.log'))
    if not log_files:
        return None

    vlm_pattern = re.compile(
        r'VLM_QUERY\|([^|]+)\|([^|]+)\|([\d.]+)\|(\d+)\|(.*)')

    queries = []
    for log_file in log_files:
        with open(log_file, 'r', errors='replace') as f:
            for line in f:
                m = vlm_pattern.search(line)
                if m:
                    queries.append({
                        'action_type': m.group(1),
                        'outcome': m.group(2),
                        'duration_sec': float(m.group(3)),
                        'attempts': int(m.group(4)),
                        'error': m.group(5) or '',
                    })

    if not queries:
        return None

    # Build summary
    summary = {'total': len(queries)}
    for outcome in VLM_OUTCOMES:
        summary[outcome] = sum(1 for q in queries if q['outcome'] == outcome)

    durations = [q['duration_sec'] for q in queries]
    success_durations = [q['duration_sec'] for q in queries if q['outcome'] == 'success']
    summary['mean_duration_sec'] = round(np.mean(durations), 2) if durations else 0
    summary['mean_success_duration_sec'] = (
        round(np.mean(success_durations), 2) if success_durations else 0)
    summary['p95_success_duration_sec'] = (
        round(np.percentile(success_durations, 95), 2) if success_durations else 0)

    return {'queries': queries, 'summary': summary}


def count_control_loop_misses(metrics_filepath):
    """Count control loop rate misses from component container isolated logs.

    Searches for ROS log files in the ros/ directory sibling to the given
    system_metrics.json file and counts lines matching the Nav2 controller
    server's "Control loop missed its desired rate" warning.

    Args:
        metrics_filepath: Path to system_metrics.json file.

    Returns:
        int: Total number of control loop misses across all matching log files.
    """
    run_dir = os.path.dirname(os.path.abspath(metrics_filepath))
    ros_dir = os.path.join(run_dir, 'ros')
    if not os.path.isdir(ros_dir):
        return 0

    pattern = os.path.join(ros_dir, 'component_container_isolated_*.log')
    log_files = glob.glob(pattern)
    if not log_files:
        return 0

    miss_pattern = re.compile(r'Control loop missed its desired rate')
    total = 0
    for log_file in log_files:
        with open(log_file, 'r', errors='replace') as f:
            for line in f:
                if miss_pattern.search(line):
                    total += 1
    return total

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

"""Export benchmark results as JSON/CSV for the static website.

Reads the run logs in opennav_benchmark_logs/ and writes a compact, committed
dataset into site/src/data/ so the website builds without the full log tree.

Every benchmark category (power mode) is declared once in CATEGORIES below.
Adding a new category, or publishing a preliminary one, is a single entry
plus a re-run of this script. Nothing in the website enumerates categories.

Usage:
    python export_site_data.py [--logs-dir DIR] [--site-dir DIR] [--strict]
"""

import argparse
import csv
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from utils import (
    METRIC_LABELS,
    PLATFORM_LABELS,
    compute_stats,
    count_completed_missions,
    count_control_loop_misses,
    load_run,
    load_vlm_queries,
    parse_planner_loop_times,
)


# --------------------------------------------------------------------------
# Configuration registry: the only place a benchmark category is named
# --------------------------------------------------------------------------

@dataclass
class RunSpec:
    """One measured run: a platform under a specific configuration."""

    key: str                     # unique within the category
    platform: str                # canonical platform key (PLATFORM_LABELS)
    label: str                   # display name for this run
    log_dir: str                 # path relative to the logs root
    tdp_w: Optional[int] = None  # TDP the platform was configured to
    note: str = ''


@dataclass
class Category:
    """A benchmark category (power mode) grouping one run per platform."""

    key: str
    label: str
    order: int
    published: bool
    description: str
    runs: List[RunSpec] = field(default_factory=list)


CATEGORIES = [
    Category(
        key='max_power',
        label='Max Power',
        order=1,
        published=True,
        description=(
            'Each platform configured to its maximum rated TDP, so the '
            'comparison reflects the most compute each board can deliver.'
        ),
        runs=[
            RunSpec('amd_strix_halo', 'amd_strix_halo', 'AMD Strix Halo',
                    'max_power/amd_strix_halo', tdp_w=120),
            RunSpec('jetson_thor', 'jetson_thor', 'NVIDIA Jetson Thor',
                    'max_power/jetson_thor', tdp_w=130),
            RunSpec('jetson_orin', 'jetson_orin', 'NVIDIA Jetson Orin',
                    'max_power/jetson_orin', tdp_w=65),
        ],
    ),
    Category(
        key='balanced_power',
        label='Balanced Power',
        order=2,
        published=True,
        description=(
            'Each platform set to a balanced power profile '
            '(except Orin AGX, max TDP 65W).'
        ),
        runs=[
            RunSpec('amd_strix_halo', 'amd_strix_halo', 'AMD Strix Halo',
                    'balanced_power/amd_strix_halo', tdp_w=85),
            RunSpec('jetson_thor_90w', 'jetson_thor', 'NVIDIA Jetson Thor (90 W)',
                    'balanced_power/jetson_thor_90w', tdp_w=90),
            RunSpec('jetson_thor_70w', 'jetson_thor', 'NVIDIA Jetson Thor (70 W)',
                    'balanced_power/jetson_thor_70w', tdp_w=70),
            RunSpec('jetson_orin', 'jetson_orin', 'NVIDIA Jetson Orin (65 W)',
                    'max_power/jetson_orin', tdp_w=65,
                    note='Kept at maximum TDP; no separate balanced run.'),
        ],
    ),
    # Preliminary; not part of the v1.3 technical report. Flip published=True
    # and re-run this script to add it to the website.
    Category(
        key='max_power_optimized',
        label='Max Power (Optimized)',
        order=3,
        published=False,
        description='Preliminary optimized-configuration runs.',
        runs=[
            RunSpec('amd_strix_halo_optimized_prelim', 'amd_strix_halo',
                    'AMD Strix Halo (optimized)',
                    'max_power_optimized/amd_strix_halo_optimized_prelim',
                    tdp_w=120),
        ],
    ),
]


# --------------------------------------------------------------------------
# Static platform reference data (README "Platforms Evaluated")
# --------------------------------------------------------------------------

# Steady-state CPU load per sensor instance, as a fraction of one core.
# Mirrors HARDWARE_PROFILES in opennav_benchmark_pipeline/scripts/
# hardware_platforms.py, measured on real Orbbec Gemini 355 and Ouster
# OS-1 32 hardware.
SENSOR_DRIVER_LOAD = {
    'jetson_orin': {'lidar_3d': 0.67, 'lidar_2d': 0.12, 'rgbd_camera': 1.55},
    'jetson_thor': {'lidar_3d': 0.22, 'lidar_2d': 0.04, 'rgbd_camera': 1.30},
    'amd_strix_halo': {'lidar_3d': 0.16, 'lidar_2d': 0.014, 'rgbd_camera': 0.52},
}

PLATFORMS = {
    'jetson_orin': {
        'key': 'jetson_orin',
        'slug': 'jetson-orin',
        'label': 'NVIDIA Jetson Orin',
        'short_label': 'Jetson AGX Orin',
        'tile_label': 'Jetson Orin',
        'vendor': 'NVIDIA',
        'vendor_url': ('https://www.nvidia.com/en-us/autonomous-machines/'
                       'embedded-systems/jetson-orin/'),
        'summary': (
            "NVIDIA's established embedded AI platform widely adopted in "
            'robotics which require edge AI such as detection, segmentation, '
            'and reinforcement learning. The Orin is the current workhorse of '
            'many production robotics deployments.'),
        'spec': {
            'cpu': '12x Arm Cortex-A78AE @ 2.2 GHz',
            'gpu_architecture': 'Ampere',
            'gpu_cores': '2048 CUDA + 64 Tensor',
            'npu_dla': '2x NVDLA 2.0',
            'ram': '64 GB LPDDR5',
            'memory_bandwidth': '204.8 GB/s',
            'tdp': '15-60 W',
        },
        'as_tested': {
            'software': 'JetPack 6.2.2, CUDA 12.6',
            'ros_distro': 'ROS 2 Jazzy',
            'dds': 'CycloneDDS',
        },
        'sensor_driver_load': SENSOR_DRIVER_LOAD['jetson_orin'],
    },
    'jetson_thor': {
        'key': 'jetson_thor',
        'slug': 'jetson-thor',
        'label': 'NVIDIA Jetson Thor',
        'short_label': 'Jetson Thor',
        'tile_label': 'Jetson Thor',
        'vendor': 'NVIDIA',
        'vendor_url': ('https://www.nvidia.com/en-us/autonomous-machines/'
                       'embedded-systems/jetson-thor/'),
        'summary': (
            "NVIDIA's next-generation embedded AI module built on the "
            'Blackwell GPU architecture. Thor is designed as the next platform '
            'for physical AI and advanced robotics applications and enables '
            'edge AI such as LLM/VLM and foundation models.'),
        'spec': {
            'cpu': '14x Arm Neoverse V3AE @ 2.6 GHz',
            'gpu_architecture': 'Blackwell',
            'gpu_cores': '2560 CUDA + 96 Tensor',
            'npu_dla': 'None',
            'ram': '128 GB LPDDR5X',
            'memory_bandwidth': '273 GB/s',
            'tdp': '40-130 W',
        },
        'as_tested': {
            'software': 'JetPack, CUDA',
            'ros_distro': 'ROS 2 Jazzy',
            'dds': 'CycloneDDS',
        },
        'sensor_driver_load': SENSOR_DRIVER_LOAD['jetson_thor'],
    },
    'amd_strix_halo': {
        'key': 'amd_strix_halo',
        'slug': 'amd-strix-halo',
        'label': 'AMD Strix Halo',
        'short_label': 'X100 / Strix Halo',
        'tile_label': 'Strix Halo',
        'vendor': 'AMD',
        'vendor_url': ('https://www.amd.com/en/products/processors/desktops/'
                       'ryzen/ryzen-ai-halo.html'),
        'summary': (
            "AMD's flagship targeting AI and robotics edge workloads. Strix "
            'Halo represents an x86-based alternative to the Jetson ecosystem, '
            'offering strong CPU performance with unified memory for LLM/VLM '
            'workloads.'),
        'spec': {
            'cpu': '16x Zen 5 (32T) @ 5.1 GHz',
            'gpu_architecture': 'RDNA 3.5',
            'gpu_cores': '2560 Shaders (40 CUs)',
            'npu_dla': 'XDNA 2 (50 TOPS)',
            'ram': 'Up to 128 GB LPDDR5X',
            'memory_bandwidth': '256 GB/s',
            'tdp': '45-120 W',
        },
        'as_tested': {
            'software': 'Ubuntu, ROCm',
            'ros_distro': 'ROS 2 Jazzy',
            'dds': 'CycloneDDS',
        },
        'sensor_driver_load': SENSOR_DRIVER_LOAD['amd_strix_halo'],
    },
}

PLATFORM_ORDER = ['amd_strix_halo', 'jetson_thor', 'jetson_orin']

# Metrics exported as full 1 Hz series, backing every chart on the site.
TIMESERIES_METRICS = [
    'cpu_total', 'cpu_freq_mhz', 'cpu_freq_ghz',
    'peak_core_util', 'mean_core_util', 'cores_active_percent',
    'gpu_util', 'gpu_clock_mhz', 'gpu_mem_clock_mhz', 'gpu_mem_used_mb',
    'gpu_mem_total_mb', 'gpu_temp', 'gpu_power_w', 'gpu_effective_throughput',
    'ram_percent', 'ram_used_mb', 'ram_total_mb', 'swap_percent',
    'board_power_w', 'cpu_temp',
    'disk_read_rate_mbps', 'disk_write_rate_mbps', 'disk_percent',
    'net_sent_rate_mbps', 'net_recv_rate_mbps', 'net_errors',
    'load_1m', 'load_5m', 'load_15m', 'process_count',
    'vcn_util', 'npu_util', 'emc_freq_mhz',
    'mem_busy_percent', 'mem_bandwidth_gbps',
]

# Rolling-stability window used by analyze_single_run.py.
ROLLING_WINDOW = 30

# Throttle point used for thermal runway, matching plot_thermal_runway().
THROTTLE_TEMP_C = 100.0

# Nav2 controller server target rate the misses are counted against.
CONTROL_LOOP_TARGET_HZ = 30.0

# Per-core utilization histogram buckets (percent).
CORE_HISTOGRAM_BINS = list(range(0, 101, 5))


# --------------------------------------------------------------------------
# Derived metrics, using the same formulas as compare_platforms.py
# --------------------------------------------------------------------------

def _core_columns(df):
    return [c for c in df.columns if c.startswith('cpu_core_')]


def _mean(df, column, default=0.0):
    if column not in df.columns:
        return default
    series = df[column].dropna()
    return float(series.mean()) if not series.empty else default


def _power_column(df):
    """Board power column, preferring the same order as compare_platforms."""
    for col in ('gpu_power_w', 'board_power_w'):
        if col in df.columns and df[col].notna().any():
            return col
    return None


def compute_derived(df):
    """Derived headroom, efficiency, and thermal figures for one run.

    Mirrors plot_resource_headroom, plot_absolute_compute_headroom,
    plot_single_thread_headroom, plot_performance_per_watt and
    plot_thermal_runway in compare_platforms.py.
    """
    core_cols = _core_columns(df)
    num_cores = len(core_cols) if core_cols else 1

    cpu_mean = _mean(df, 'cpu_total')
    freq_ghz = _mean(df, 'cpu_freq_ghz', default=1.0) or 1.0
    gpu_mean = _mean(df, 'gpu_util')

    total_ghz_cores = num_cores * freq_ghz
    used_ghz_cores = (cpu_mean / 100.0) * total_ghz_cores
    avail_ghz_cores = total_ghz_cores - used_ghz_cores

    derived = {
        'num_cores': num_cores,
        'cpu_mean_percent': round(cpu_mean, 2),
        'cpu_available_percent': round(100 - cpu_mean, 2),
        'free_core_equivalents': round((100 - cpu_mean) / 100.0 * num_cores, 2),
        'cpu_freq_ghz': round(freq_ghz, 3),
        'total_ghz_cores': round(total_ghz_cores, 2),
        'used_ghz_cores': round(used_ghz_cores, 2),
        'available_ghz_cores': round(avail_ghz_cores, 2),
        'gpu_mean_percent': round(gpu_mean, 2),
        'gpu_available_percent': round(100 - gpu_mean, 2),
    }

    # Single-thread headroom: least-loaded core per sample, median across run.
    if core_cols and 'cpu_freq_ghz' in df.columns:
        median_min_util = float(df[core_cols].min(axis=1).median())
        derived['least_loaded_core_percent'] = round(median_min_util, 2)
        derived['single_thread_headroom_ghz'] = round(
            (100 - median_min_util) / 100.0 * freq_ghz, 3)

    # Memory.
    ram_mean = _mean(df, 'ram_percent')
    derived['ram_mean_percent'] = round(ram_mean, 2)
    derived['ram_available_percent'] = round(100 - ram_mean, 2)
    if 'ram_total_mb' in df.columns:
        ram_total = _mean(df, 'ram_total_mb')
        ram_used = _mean(df, 'ram_used_mb')
        derived['ram_total_mb'] = round(ram_total, 1)
        derived['ram_used_mb'] = round(ram_used, 1)
        derived['ram_free_mb'] = round(ram_total - ram_used, 1)

    if 'gpu_mem_total_mb' in df.columns and 'gpu_mem_used_mb' in df.columns:
        vram_total = _mean(df, 'gpu_mem_total_mb')
        vram_used = _mean(df, 'gpu_mem_used_mb')
        derived['vram_total_mb'] = round(vram_total, 1)
        derived['vram_used_mb'] = round(vram_used, 1)
        derived['vram_free_mb'] = round(vram_total - vram_used, 1)
        derived['vram_free_percent'] = (
            round((vram_total - vram_used) / vram_total * 100, 2)
            if vram_total > 0 else 0.0)

    # Power and efficiency.
    power_col = _power_column(df)
    if power_col:
        mean_power = _mean(df, power_col)
        derived['mean_power_w'] = round(mean_power, 2)
        derived['power_source_metric'] = power_col
        if mean_power > 0:
            derived['ghz_cores_per_watt'] = round(avail_ghz_cores / mean_power, 4)
            derived['gpu_percent_per_watt'] = round(gpu_mean / mean_power, 4)

    # Thermal runway: margin to the throttle point.
    if 'cpu_temp' in df.columns:
        derived['cpu_thermal_margin_c'] = round(
            THROTTLE_TEMP_C - _mean(df, 'cpu_temp'), 2)
    if 'gpu_temp' in df.columns:
        derived['gpu_thermal_margin_c'] = round(
            THROTTLE_TEMP_C - _mean(df, 'gpu_temp'), 2)

    return derived


def compute_radar_raw(df):
    """Raw (un-normalized) radar dimension values for one run.

    Mirrors plot_platform_balance_radar() in compare_platforms.py.
    """
    core_cols = _core_columns(df)
    num_cores = len(core_cols) if core_cols else 1
    freq = _mean(df, 'cpu_freq_ghz', default=1.0) or 1.0

    if 'gpu_mem_total_mb' in df.columns and 'gpu_mem_used_mb' in df.columns:
        mem_total = _mean(df, 'gpu_mem_total_mb')
        mem_used = _mean(df, 'gpu_mem_used_mb')
    elif 'ram_total_mb' in df.columns and 'ram_used_mb' in df.columns:
        mem_total = _mean(df, 'ram_total_mb')
        mem_used = _mean(df, 'ram_used_mb')
    else:
        mem_total = mem_used = 0.0

    return {
        'CPU Headroom': 100 - _mean(df, 'cpu_total'),
        'CPU Capability': num_cores * freq,
        'GPU Capability': _mean(df, 'gpu_util'),
        'Memory Capability': _mean(df, 'ram_total_mb') / 1000.0,
        'Memory Headroom': ((mem_total - mem_used) / mem_total * 100
                            if mem_total > 0 else 0.0),
        'Clock Speed': freq,
    }


RADAR_DIMENSIONS = [
    'CPU Headroom', 'CPU Capability', 'GPU Capability',
    'Memory Capability', 'Memory Headroom', 'Clock Speed',
]


def normalize_radar(raw_by_run):
    """Min-max normalize each radar dimension to 0-1 across runs."""
    normalized = {}
    for run_key, vals in raw_by_run.items():
        scores = {}
        for dim in RADAR_DIMENSIONS:
            all_vals = [raw_by_run[k][dim] for k in raw_by_run]
            max_val = max(all_vals) if max(all_vals) > 0 else 1
            scores[dim] = round(vals[dim] / max_val, 4)
        normalized[run_key] = scores
    return normalized


# --------------------------------------------------------------------------
# Per-run extraction
# --------------------------------------------------------------------------

def _series(df, column):
    """A JSON-safe list for one metric, or None if the run lacks it."""
    if column not in df.columns:
        return None
    series = df[column]
    if series.isna().all():
        return None
    return [None if (v is None or (isinstance(v, float) and np.isnan(v)))
            else round(float(v), 3) for v in series]


def build_timeseries(df):
    """1 Hz series, per-core matrix, histogram and rolling stability."""
    out = {
        'elapsed_sec': [int(v) for v in df['elapsed_sec']]
        if 'elapsed_sec' in df.columns else list(range(len(df))),
        'metrics': {},
    }

    for metric in TIMESERIES_METRICS:
        values = _series(df, metric)
        if values is not None:
            out['metrics'][metric] = values

    core_cols = _core_columns(df)
    if core_cols:
        matrix = df[core_cols].to_numpy(dtype=float)
        out['cores'] = {
            'count': len(core_cols),
            # cores x samples, rounded to whole percent for size
            'matrix': [[round(float(v), 1) for v in row] for row in matrix.T],
        }
        counts, _ = np.histogram(matrix.flatten(), bins=CORE_HISTOGRAM_BINS)
        out['core_histogram'] = {
            'bins': CORE_HISTOGRAM_BINS,
            'counts': [int(c) for c in counts],
        }
        out['core_percentiles'] = {
            f'p{p}': [round(float(np.percentile(matrix[:, i], p)), 2)
                      for i in range(matrix.shape[1])]
            for p in (50, 95, 99)
        }
        out['peak_core_index'] = int(np.argmax(matrix.mean(axis=0)))
        out['core_means'] = [round(float(v), 2) for v in matrix.mean(axis=0)]

    # Rolling stability: same 30-sample window as analyze_single_run.py.
    stability = {}
    for metric in ('cpu_total', 'gpu_util'):
        if metric in df.columns:
            rolled = df[metric].rolling(ROLLING_WINDOW).std()
            stability[metric] = [
                None if np.isnan(v) else round(float(v), 3) for v in rolled]
    if stability:
        out['rolling_std'] = {'window': ROLLING_WINDOW, 'series': stability}

    return out


def build_run_record(category, spec, logs_dir):
    """Load one run and return (record, timeseries) or (None, None)."""
    metrics_path = os.path.join(logs_dir, spec.log_dir, 'system_metrics.json')
    if not os.path.isfile(metrics_path):
        print(f'  skip {category.key}/{spec.key}: {metrics_path} not found')
        return None, None

    meta, df = load_run(metrics_path)
    if df.empty:
        print(f'  skip {category.key}/{spec.key}: no samples')
        return None, None

    stats_df = compute_stats(df)
    stats = {}
    for metric, row in stats_df.iterrows():
        if metric.startswith('cpu_core_'):
            continue
        stats[metric] = {
            'label': METRIC_LABELS.get(metric, metric),
            'mean': _num(row['mean']),
            'std': _num(row['std']),
            'min': _num(row['min']),
            'max': _num(row['max']),
            'p50': _num(row['p50']),
            'p95': _num(row['p95']),
            'p99': _num(row['p99']),
        }

    duration = meta.get('duration_sec') or len(df)
    misses = count_control_loop_misses(metrics_path)
    planner = parse_planner_loop_times(metrics_path)
    vlm = load_vlm_queries(metrics_path)

    record = {
        'id': f'{category.key}__{spec.key}',
        'category': category.key,
        'run_key': spec.key,
        'platform': spec.platform,
        'platform_label': PLATFORM_LABELS.get(spec.platform, spec.platform),
        'label': spec.label,
        'tdp_w': spec.tdp_w,
        'note': spec.note,
        'log_dir': spec.log_dir,
        'duration_sec': duration,
        'actual_samples': meta.get('actual_samples', len(df)),
        'application': {
            'completed_missions': count_completed_missions(metrics_path),
            'control_loop_misses': misses,
            'control_loop_misses_per_sec': (
                round(misses / duration, 3) if duration else None),
            'control_loop_target_hz': CONTROL_LOOP_TARGET_HZ,
        },
        'derived': compute_derived(df),
        'stats': stats,
    }

    if planner:
        record['application']['planner_cycle_sec'] = {
            k: planner[k] for k in
            ('count', 'mean', 'std', 'min', 'max', 'p50', 'p95', 'p99')
        }
    if vlm:
        record['application']['vlm'] = vlm['summary']
        record['application']['vlm']['durations_sec'] = [
            q['duration_sec'] for q in vlm['queries']]
        record['application']['vlm']['success_durations_sec'] = [
            q['duration_sec'] for q in vlm['queries'] if q['outcome'] == 'success']

    return record, build_timeseries(df)


def _num(value):
    """Round-trip a numpy scalar to a JSON-safe number (or None)."""
    if value is None:
        return None
    value = float(value)
    return None if np.isnan(value) else round(value, 3)


# --------------------------------------------------------------------------
# Registry reconciliation
# --------------------------------------------------------------------------

# A run directory is identified by the metrics file the exporter reads.
RUN_MARKER = 'system_metrics.json'


def declared_log_dirs():
    """Map every log_dir named in CATEGORIES to the categories using it.

    Keyed by log_dir rather than by category, because a run may legitimately
    be shared: balanced_power reuses max_power/jetson_orin.
    """
    declared = {}
    for category in CATEGORIES:
        for spec in category.runs:
            declared.setdefault(spec.log_dir, []).append(category)
    return declared


def log_dirs_on_disk(logs_dir):
    """Every directory under the logs root holding a run's metrics file."""
    found = set()
    for root, _dirs, files in os.walk(logs_dir):
        if RUN_MARKER in files:
            found.add(os.path.relpath(root, logs_dir))
    return found


def check_registry(logs_dir):
    """Reconcile the log tree against CATEGORIES, both directions.

    Returns a list of human-readable problems; empty means consistent.
    """
    declared = declared_log_dirs()
    on_disk = log_dirs_on_disk(logs_dir)
    problems = []

    for path in sorted(on_disk - set(declared)):
        problems.append(
            f'{path}: holds a run but is not declared in CATEGORIES, so it '
            f'will never reach the website. Add a RunSpec for it (it needs a '
            f'label and a tdp_w) under the category it belongs to.')

    for path, categories in sorted(declared.items()):
        if path in on_disk:
            continue
        # Unpublished categories may legitimately reference work in progress.
        keys = sorted(c.key for c in categories if c.published)
        if not keys:
            continue
        problems.append(
            f'{path}: declared by published category {", ".join(keys)} but no '
            f'{RUN_MARKER} found there, so that run is silently missing from '
            f'the site. Restore the logs or repoint RunSpec.log_dir.')

    return problems


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------

def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write('\n')


def write_run_csv(path, timeseries):
    """One CSV per run so readers can download the underlying samples."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    metrics = sorted(timeseries['metrics'])
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['elapsed_sec'] + metrics)
        for i, elapsed in enumerate(timeseries['elapsed_sec']):
            writer.writerow(
                [elapsed] + [timeseries['metrics'][m][i] for m in metrics])


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs-dir',
                        default=os.path.join(repo, 'opennav_benchmark_logs'))
    parser.add_argument('--site-dir', default=os.path.join(repo, 'site'))
    parser.add_argument(
        '--strict', action='store_true',
        help='fail if the log tree and CATEGORIES disagree, before exporting')
    args = parser.parse_args()

    if args.strict:
        problems = check_registry(args.logs_dir)
        if problems:
            print('Registry check failed:')
            for problem in problems:
                print(f'  {problem}')
            return 1
        print('Registry check passed: log tree matches CATEGORIES\n')

    data_dir = os.path.join(args.site_dir, 'src', 'data')
    public_dir = os.path.join(args.site_dir, 'public', 'data')

    categories_out = []
    runs_out = []
    derived_out = {}

    for category in sorted(CATEGORIES, key=lambda c: c.order):
        if not category.published:
            print(f'{category.key}: unpublished, skipping')
            continue

        print(f'{category.key}:')
        records = []
        timeseries_by_run = {}
        for spec in category.runs:
            record, timeseries = build_run_record(category, spec, args.logs_dir)
            if record is None:
                continue
            records.append(record)
            timeseries_by_run[spec.key] = timeseries
            print(f'  {spec.key}: {record["actual_samples"]} samples, '
                  f'{record["application"]["completed_missions"]} missions')

        if not records:
            print(f'  {category.key}: no runs found, omitting from site data')
            continue

        for record in records:
            write_json(
                os.path.join(data_dir, 'timeseries',
                             f'{category.key}__{record["run_key"]}.json'),
                timeseries_by_run[record['run_key']])
            write_run_csv(
                os.path.join(public_dir, 'csv',
                             f'{category.key}__{record["run_key"]}.csv'),
                timeseries_by_run[record['run_key']])

        raw_radar = {}
        for spec in category.runs:
            if spec.key not in timeseries_by_run:
                continue
            metrics_path = os.path.join(
                args.logs_dir, spec.log_dir, 'system_metrics.json')
            _, df = load_run(metrics_path)
            raw_radar[spec.key] = compute_radar_raw(df)

        derived_out[category.key] = {
            'radar': {
                'dimensions': RADAR_DIMENSIONS,
                'raw': {k: {d: round(v, 4) for d, v in vals.items()}
                        for k, vals in raw_radar.items()},
                'normalized': normalize_radar(raw_radar),
            },
            'efficiency': {
                r['run_key']: {
                    'label': r['label'],
                    'platform': r['platform'],
                    **r['derived'],
                } for r in records
            },
        }

        categories_out.append({
            'key': category.key,
            'label': category.label,
            'order': category.order,
            'description': category.description,
            'run_keys': [r['run_key'] for r in records],
        })
        runs_out.extend(records)

    write_json(os.path.join(data_dir, 'categories.json'), categories_out)
    write_json(os.path.join(data_dir, 'runs.json'), runs_out)
    write_json(os.path.join(data_dir, 'derived.json'), derived_out)
    write_json(os.path.join(data_dir, 'platforms.json'), {
        'order': PLATFORM_ORDER,
        'platforms': PLATFORMS,
        'metric_labels': METRIC_LABELS,
    })
    write_json(os.path.join(public_dir, 'dataset.json'), {
        'categories': categories_out,
        'platforms': PLATFORMS,
        'runs': runs_out,
        'derived': derived_out,
    })

    print(f'\nWrote {len(runs_out)} runs across {len(categories_out)} '
          f'categories to {data_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

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

"""
Capture system metrics for the robotics workload benchmark.

Auto-detects platform (AMD Ryzen AI Max+, NVIDIA Jetson Orin, Jetson Thor)
and captures platform-specific GPU metrics alongside common system metrics.

Usage:
    ./capture_system_metrics.py <output_dir> <duration_seconds>

Output:
    Writes a JSON file to <output_dir>/system_metrics_<timestamp>.json
"""

import json
import os
import signal
import sys
import time

import psutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hardware_platforms import detect_platform, AmdGpuMetrics, JetsonGpuMetrics


def collect_common_metrics():
    """Collect platform-independent system metrics via psutil."""
    metrics = {}

    metrics['timestamp'] = int(time.time())

    # CPU
    metrics['cpu_total'] = psutil.cpu_percent(interval=0)
    metrics['cpu_cores'] = psutil.cpu_percent(percpu=True)

    freq = psutil.cpu_freq()
    if freq:
        metrics['cpu_freq_mhz'] = round(freq.current, 1)

    # Memory
    vm = psutil.virtual_memory()
    metrics['ram_percent'] = vm.percent
    metrics['ram_used_mb'] = round(vm.used / (1024 * 1024), 1)
    metrics['ram_total_mb'] = round(vm.total / (1024 * 1024), 1)
    metrics['swap_percent'] = psutil.swap_memory().percent

    # Disk
    metrics['disk_percent'] = psutil.disk_usage('/').percent
    try:
        disk_io = psutil.disk_io_counters()
        if disk_io:
            metrics['disk_read_mb'] = round(disk_io.read_bytes / (1024 * 1024), 1)
            metrics['disk_write_mb'] = round(disk_io.write_bytes / (1024 * 1024), 1)
    except RuntimeError:
        pass

    # Network
    try:
        net = psutil.net_io_counters()
        if net:
            metrics['net_sent_mb'] = round(net.bytes_sent / (1024 * 1024), 1)
            metrics['net_recv_mb'] = round(net.bytes_recv / (1024 * 1024), 1)
            metrics['net_errors'] = net.errin + net.errout
    except RuntimeError:
        pass

    # Load average
    try:
        load1, load5, load15 = os.getloadavg()
        metrics['load_1m'] = round(load1, 2)
        metrics['load_5m'] = round(load5, 2)
        metrics['load_15m'] = round(load15, 2)
    except OSError:
        pass

    # Process count
    metrics['process_count'] = len(psutil.pids())

    # CPU temperature
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Pick the first available CPU-related sensor
            for name in ['coretemp', 'k10temp', 'cpu_thermal',
                         'Tctl', 'zenpower', 'acpitz']:
                if name in temps and temps[name]:
                    metrics['cpu_temp'] = temps[name][0].current
                    break
            # Fallback: just use the first available sensor
            if 'cpu_temp' not in metrics:
                for name, entries in temps.items():
                    if entries:
                        metrics['cpu_temp'] = entries[0].current
                        break
    except (AttributeError, RuntimeError):
        pass

    # Override: prefer cpu-thermal zone when available (e.g. Jetson)
    # psutil may find an external board sensor instead of the SoC thermal zone
    try:
        import glob as _glob
        for tz_type in sorted(_glob.glob('/sys/class/thermal/thermal_zone*/type')):
            with open(tz_type, 'r') as f:
                if f.read().strip() == 'cpu-thermal':
                    temp_path = os.path.join(
                        os.path.dirname(tz_type), 'temp')
                    with open(temp_path, 'r') as f2:
                        metrics['cpu_temp'] = round(
                            int(f2.read().strip()) / 1000.0, 1)
                    break
    except (OSError, ValueError):
        pass

    return metrics


def write_json(filepath, data):
    """Atomically write data to a JSON file."""
    tmp = filepath + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, filepath)


def main():
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <output_dir> <duration_seconds>')
        sys.exit(1)

    run_dir = sys.argv[1]
    duration = int(sys.argv[2])

    if not os.path.isdir(run_dir):
        os.makedirs(run_dir, exist_ok=True)

    # Detect platform
    platform = detect_platform()
    print(f'Detected platform: {platform}')

    # Initialize GPU metrics collector
    if platform == 'amd_strix_halo':
        gpu = AmdGpuMetrics()
    elif platform in ('jetson_orin', 'jetson_thor'):
        gpu = JetsonGpuMetrics(variant=platform)
    else:
        raise RuntimeError(
            f"Unsupported platform: '{platform}'. "
            f"Please add support in hardware_platforms.py."
        )

    # Output file
    start_time = int(time.time())
    filename = os.path.join(run_dir, f'system_metrics_{start_time}.json')
    print(f'Writing metrics to: {filename}')

    # Data structure
    output = {
        'platform': platform,
        'start_time': start_time,
        'duration_sec': duration,
        'samples': []
    }

    # Signal handling for graceful shutdown
    shutdown = False

    def handle_signal(signum, frame):
        nonlocal shutdown
        print(f'Received signal {signum}, shutting down...')
        shutdown = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Prime psutil CPU measurement (first call always returns 0)
    psutil.cpu_percent(interval=0)
    psutil.cpu_percent(percpu=True)

    flush_interval = 30
    last_flush = time.monotonic()

    print(f'Capturing metrics every 1s for {duration}s...')

    elapsed = 0
    while elapsed < duration and not shutdown:
        loop_start = time.monotonic()

        # Collect metrics
        sample = collect_common_metrics()
        gpu_metrics = gpu.collect()
        sample.update(gpu_metrics)
        output['samples'].append(sample)

        # Periodic flush to disk
        now = time.monotonic()
        if now - last_flush >= flush_interval:
            write_json(filename, output)
            last_flush = now

        # Sleep for remainder of 1-second interval
        sleep_time = 1.0 - (time.monotonic() - loop_start)
        if sleep_time > 0 and not shutdown:
            time.sleep(sleep_time)

        elapsed += 1

    # Final write
    output['end_time'] = int(time.time())
    output['actual_samples'] = len(output['samples'])
    write_json(filename, output)
    print(f'Metrics capture complete. {len(output["samples"])} samples written to {filename}')


if __name__ == '__main__':
    main()

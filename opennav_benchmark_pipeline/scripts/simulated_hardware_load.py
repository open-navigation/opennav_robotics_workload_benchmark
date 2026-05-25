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
Simulate sensor driver CPU load for the robotics workload benchmark.

Generates steady-state CPU load matching what real sensor drivers would
consume on the detected hardware platform.

Usage:
    ./simulated_hardware_load.py [--lidar-3d N] [--lidar-2d N] [--rgbd-cameras N] [--duration S]
"""

import argparse
import math
import multiprocessing
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hardware_platforms import detect_platform, HARDWARE_PROFILES


def cpu_burn_full(stop_event):
    """Worker that burns 100% of one core until stopped."""
    while not stop_event.is_set():
        pass


def cpu_burn_fractional(duty_cycle, stop_event):
    """Worker that burns a fraction of one core using duty cycling.

    Args:
        duty_cycle: Fraction of time to busy-loop (0.0 to 1.0).
        stop_event: Multiprocessing event to signal shutdown.
    """
    cycle_sec = 0.1  # 100ms cycle
    busy_sec = duty_cycle * cycle_sec
    sleep_sec = cycle_sec - busy_sec
    while not stop_event.is_set():
        end = time.monotonic() + busy_sec
        while time.monotonic() < end:
            pass
        if sleep_sec > 0:
            time.sleep(sleep_sec)


def compute_total_load(profile, num_3d, num_2d, num_rgbd):
    """Compute total CPU load in units of cores."""
    return (profile['lidar_3d'] * num_3d +
            profile['lidar_2d'] * num_2d +
            profile['rgbd_camera'] * num_rgbd)


def main():
    parser = argparse.ArgumentParser(
        description='Simulate sensor driver CPU load for benchmarking.')
    parser.add_argument('--lidar-3d', type=int, default=3,
                        help='Number of 3D LiDARs (default: 3)')
    parser.add_argument('--lidar-2d', type=int, default=2,
                        help='Number of 2D LiDARs (default: 2)')
    parser.add_argument('--rgbd-cameras', type=int, default=3,
                        help='Number of RGBD cameras (default: 3)')
    parser.add_argument('--duration', type=int, default=0,
                        help='Run for N seconds (0 = run until killed, default: 0)')
    args = parser.parse_args()

    platform = detect_platform()
    profile = HARDWARE_PROFILES.get(platform, HARDWARE_PROFILES['amd_ryzenai_maxplus_395'])

    total_load = compute_total_load(
        profile, args.lidar_3d, args.lidar_2d, args.rgbd_cameras)

    full_workers = int(math.floor(total_load))
    fractional = total_load - full_workers
    num_workers = full_workers + (1 if fractional > 0.001 else 0)

    print(f"Platform: {platform}")
    print(f"Profile: {profile}")
    print(f"Sensors: {args.lidar_3d} 3D LiDAR, {args.lidar_2d} 2D LiDAR, "
          f"{args.rgbd_cameras} RGBD cameras")
    print(f"Total load target: {total_load:.3f} cores "
          f"({full_workers} full + {fractional:.3f} fractional)")
    print(f"Spawning {num_workers} worker process(es)")
    sys.stdout.flush()

    if num_workers == 0:
        print("No load to generate (total load is zero). Exiting.")
        return

    stop_event = multiprocessing.Event()
    workers = []

    for _ in range(full_workers):
        p = multiprocessing.Process(target=cpu_burn_full, args=(stop_event,))
        p.daemon = True
        p.start()
        workers.append(p)

    if fractional > 0.001:
        p = multiprocessing.Process(
            target=cpu_burn_fractional, args=(fractional, stop_event))
        p.daemon = True
        p.start()
        workers.append(p)

    def shutdown(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        sys.stdout.flush()
        stop_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    if args.duration > 0:
        end_time = time.monotonic() + args.duration
        while not stop_event.is_set() and time.monotonic() < end_time:
            time.sleep(0.5)
        stop_event.set()
    else:
        while not stop_event.is_set():
            time.sleep(1.0)

    for p in workers:
        p.join(timeout=5)
        if p.is_alive():
            p.kill()

    print("Hardware load simulation stopped.")


if __name__ == '__main__':
    main()

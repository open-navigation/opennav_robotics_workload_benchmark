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


def cpu_burn_fractional(duty_cycle, stop_event):
    """Worker that burns a fraction of one core using duty cycling.

    Args:
        duty_cycle: Fraction of time to busy-loop (0.0 to 1.0).
        stop_event: Multiprocessing event to signal shutdown.
    """
    if duty_cycle >= 1.0:
        while not stop_event.is_set():
            pass
    else:
        cycle_sec = 0.1  # 100ms cycle
        busy_sec = duty_cycle * cycle_sec
        sleep_sec = cycle_sec - busy_sec
        while not stop_event.is_set():
            end = time.monotonic() + busy_sec
            while time.monotonic() < end:
                pass
            if sleep_sec > 0:
                time.sleep(sleep_sec)


def build_sensor_list(profile, num_3d, num_2d, num_rgbd):
    """Build a flat list of (label, cpu_load) for each sensor instance."""
    sensors = []
    for i in range(num_3d):
        sensors.append((f'3d_lidar_{i}', profile['lidar_3d']))
    for i in range(num_2d):
        sensors.append((f'2d_lidar_{i}', profile['lidar_2d']))
    for i in range(num_rgbd):
        sensors.append((f'rgbd_camera_{i}', profile['rgbd_camera']))
    return sensors


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
    profile = HARDWARE_PROFILES.get(platform, HARDWARE_PROFILES['amd_strix_halo'])

    sensors = build_sensor_list(
        profile, args.lidar_3d, args.lidar_2d, args.rgbd_cameras)
    total_load = sum(load for _, load in sensors)

    print(f"Platform: {platform}")
    print(f"Profile: {profile}")
    print(f"Sensors: {args.lidar_3d} 3D LiDAR, {args.lidar_2d} 2D LiDAR, "
          f"{args.rgbd_cameras} RGBD cameras")
    print(f"Total load target: {total_load:.3f} cores")
    num_processes = 0
    for label, load in sensors:
        n_full = int(math.floor(load))
        frac = load - n_full
        n_procs = n_full + (1 if frac > 0.001 else 0)
        num_processes += n_procs
        print(f"  {label}: {load:.3f} cores ({n_procs} process(es))")
    print(f"Spawning {num_processes} worker process(es) "
          f"for {len(sensors)} sensor(s)")
    sys.stdout.flush()

    if not sensors:
        print("No load to generate (no sensors configured). Exiting.")
        return

    stop_event = multiprocessing.Event()
    workers = []

    for label, load in sensors:
        n_full = int(math.floor(load))
        frac = load - n_full
        for j in range(n_full):
            p = multiprocessing.Process(
                target=cpu_burn_fractional, args=(1.0, stop_event),
                name=f'{label}_full_{j}')
            p.daemon = True
            p.start()
            workers.append(p)
        if frac > 0.001:
            p = multiprocessing.Process(
                target=cpu_burn_fractional, args=(frac, stop_event),
                name=f'{label}_frac')
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

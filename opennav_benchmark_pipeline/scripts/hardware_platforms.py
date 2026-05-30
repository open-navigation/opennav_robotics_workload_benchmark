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

"""Hardware platform detection and GPU metrics for the robotics workload benchmark."""

import glob
import os


def detect_platform():
    """Detect the hardware platform. Returns one of:
    'jetson_orin', 'jetson_thor', 'amd_strix_halo', 'unknown'."""
    # Check for Jetson via device-tree model
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
        if 'jetson' in model or 'tegra' in model:
            # Thor uses tegra264 SoC, Orin uses tegra234
            if 'thor' in model or 'tegra264' in model:
                return 'jetson_thor'
            return 'jetson_orin'
    except (FileNotFoundError, PermissionError):
        pass

    # Fallback Jetson check
    if os.path.exists('/etc/nv_tegra_release'):
        return 'jetson_orin'

    # Check for AMD CPU
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
        if 'AuthenticAMD' in cpuinfo or 'AMD' in cpuinfo:
            return 'amd_strix_halo'
    except (FileNotFoundError, PermissionError):
        pass

    return 'unknown'


# Hardware profiles: steady-state CPU utilization per sensor instance,
# expressed as a fraction of one CPU core (e.g., 0.15 = 15% of one core).
HARDWARE_PROFILES = {
    'jetson_orin': {
        'lidar_3d': 0.67,
        'lidar_2d': 0.12,
        'rgbd_camera': 1.55,
    },
    'jetson_thor': {
        'lidar_3d': 0.22,
        'lidar_2d': 0.04,
        'rgbd_camera': 1.30,
    },
    'amd_strix_halo': {
        'lidar_3d': 0.16, 
        'lidar_2d': 0.014,
        'rgbd_camera': 0.52,
    },
}


class GpuMetrics:
    """Base GPU metrics collector (no-op for unknown platforms)."""

    def __init__(self):
        self._warnings_issued = set()

    def _read_sysfs(self, path, cast=int):
        """Read a single value from a sysfs file. Returns None on failure."""
        try:
            with open(path, 'r') as f:
                return cast(f.read().strip())
        except (FileNotFoundError, PermissionError, ValueError, TypeError, OSError) as e:
            key = path
            if key not in self._warnings_issued:
                self._warnings_issued.add(key)
                print(f'Warning: cannot read {path}: {e}')
            return None

    def _find_sysfs(self, pattern):
        """Return the first match for a glob pattern, or None."""
        matches = sorted(glob.glob(pattern))
        return matches[0] if matches else None

    def collect(self):
        """Return a dict of GPU metrics. Override in subclasses."""
        return {}


class AmdGpuMetrics(GpuMetrics):
    """Collect GPU metrics for AMD GPUs via amdgpu sysfs."""

    def __init__(self):
        super().__init__()
        # Locate the amdgpu device directory
        self._dev = self._find_sysfs('/sys/class/drm/card*/device/gpu_busy_percent')
        if self._dev:
            self._dev = os.path.dirname(self._dev)
        else:
            # Try to find any amdgpu device
            vendor_paths = glob.glob('/sys/class/drm/card*/device/vendor')
            for vp in sorted(vendor_paths):
                try:
                    with open(vp, 'r') as f:
                        if f.read().strip() == '0x1002':
                            self._dev = os.path.dirname(vp)
                            break
                except (OSError, ValueError):
                    continue
            if not self._dev:
                print('Warning: no AMD GPU device found in sysfs')

        # Locate hwmon directory for temperature and power
        self._hwmon = None
        if self._dev:
            hwmon_match = self._find_sysfs(os.path.join(self._dev, 'hwmon', 'hwmon*'))
            if hwmon_match:
                self._hwmon = hwmon_match

    def collect(self):
        metrics = {}
        if not self._dev:
            return metrics

        # GPU utilization
        val = self._read_sysfs(os.path.join(self._dev, 'gpu_busy_percent'))
        if val is not None:
            metrics['gpu_util'] = val

        # VRAM usage
        vram_used = self._read_sysfs(os.path.join(self._dev, 'mem_info_vram_used'))
        if vram_used is not None:
            metrics['gpu_mem_used_mb'] = round(vram_used / (1024 * 1024), 1)

        vram_total = self._read_sysfs(os.path.join(self._dev, 'mem_info_vram_total'))
        if vram_total is not None:
            metrics['gpu_mem_total_mb'] = round(vram_total / (1024 * 1024), 1)

        # GPU clock (parse active frequency marked with *)
        gpu_clock = self._read_gpu_clock()
        if gpu_clock is not None:
            metrics['gpu_clock_mhz'] = gpu_clock

        # GPU temperature and power from hwmon
        if self._hwmon:
            # Temperature - edge temp is typically temp1
            temp = self._read_sysfs(os.path.join(self._hwmon, 'temp1_input'))
            if temp is not None:
                metrics['gpu_temp'] = round(temp / 1000.0, 1)

            # Power (average, in microwatts)
            power = self._read_sysfs(os.path.join(self._hwmon, 'power1_average'))
            if power is not None:
                metrics['gpu_power_w'] = round(power / 1_000_000.0, 2)

        # Video codec engine utilization
        vcn = self._read_sysfs(os.path.join(self._dev, 'vcn_busy_percent'))
        if vcn is not None:
            metrics['vcn_util'] = vcn

        # Memory clock
        mem_clock = self._read_dpm_clock('pp_dpm_mclk')
        if mem_clock is not None:
            metrics['gpu_mem_clock_mhz'] = mem_clock

        # Memory controller utilization and bandwidth
        mem_busy_path = os.path.join(self._dev, 'mem_busy_percent')
        mem_busy = self._read_sysfs(mem_busy_path) if os.path.exists(mem_busy_path) else None
        if mem_busy is not None:
            metrics['mem_busy_percent'] = mem_busy
            # AMD Strix Halo: LPDDR5X-7500 with 256-bit bus = ~120 GB/s theoretical max
            metrics['mem_bandwidth_gbps'] = round((mem_busy / 100.0) * 120.0, 2)

        # NPU (XDNA) - best effort
        npu_metrics = self._read_npu()
        metrics.update(npu_metrics)

        return metrics

    def _read_dpm_clock(self, filename):
        """Parse a pp_dpm_*clk file to find the active clock frequency."""
        path = os.path.join(self._dev, filename)
        try:
            with open(path, 'r') as f:
                for line in f:
                    if '*' in line:
                        parts = line.split()
                        for part in parts:
                            part_lower = part.lower().rstrip('*')
                            if 'mhz' in part_lower:
                                return int(part_lower.replace('mhz', ''))
        except (FileNotFoundError, PermissionError, ValueError, OSError):
            pass
        return None

    def _read_gpu_clock(self):
        """Parse pp_dpm_sclk to find the active GPU clock frequency."""
        return self._read_dpm_clock('pp_dpm_sclk')

    def _read_npu(self):
        """Attempt to read AMD XDNA NPU metrics."""
        metrics = {}
        # Check for accel devices
        accel_path = self._find_sysfs('/sys/class/accel/accel*')
        if not accel_path:
            return metrics
        # Try to read NPU status if available
        status_path = os.path.join(accel_path, 'device', 'npu_busy_percent')
        if not os.path.exists(status_path):
            return metrics
        val = self._read_sysfs(status_path)
        if val is not None:
            metrics['npu_util'] = val
        return metrics


class JetsonGpuMetrics(GpuMetrics):
    """Collect GPU metrics for NVIDIA Jetson (Orin / Thor) via sysfs."""

    def __init__(self, variant='jetson_orin'):
        super().__init__()
        self._variant = variant

        # GPU load path - varies by Jetson generation and JetPack version
        # Orin (tegra234): /sys/devices/platform/17000000.ga10b/load
        # Thor (tegra264): discrete GPU over PCIe, no sysfs load file;
        #                   fall back to nvidia-smi
        self._gpu_load_path = None
        self._nvml_handle = None
        load_candidates = glob.glob('/sys/devices/platform/17000000.ga10b/load')
        load_candidates += glob.glob('/sys/devices/platform/*.gpu/load')
        load_candidates += glob.glob('/sys/devices/platform/bus@0/17000000.gpu/load')
        load_candidates += glob.glob('/sys/devices/platform/bus@0/*.gpu/load')
        load_candidates += glob.glob('/sys/devices/gpu.0/load')
        for candidate in sorted(load_candidates):
            if os.path.exists(candidate):
                self._gpu_load_path = candidate
                break
        if not self._gpu_load_path:
            try:
                import pynvml
                pynvml.nvmlInit()
                self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                pass

        # GPU frequency path
        # Orin: /sys/devices/platform/17000000.ga10b/devfreq/17000000.ga10b/cur_freq
        # Thor: /sys/class/devfreq/gpu-gpc-0/cur_freq (dual clock domains)
        self._gpu_freq_path = None
        self._gpu_freq_paths = []
        freq_candidates = glob.glob(
            '/sys/devices/platform/17000000.ga10b/devfreq/*/cur_freq')
        freq_candidates += glob.glob('/sys/devices/platform/*.gpu/devfreq/*/cur_freq')
        freq_candidates += glob.glob(
            '/sys/devices/platform/bus@0/17000000.gpu/devfreq/*/cur_freq')
        freq_candidates += glob.glob(
            '/sys/devices/platform/bus@0/*.gpu/devfreq/*/cur_freq')
        freq_candidates += glob.glob('/sys/class/devfreq/gpu-gpc-*/cur_freq')
        freq_candidates += glob.glob('/sys/class/devfreq/gpu-nvd-*/cur_freq')
        freq_candidates += glob.glob('/sys/devices/gpu.0/devfreq/*/cur_freq')
        if freq_candidates:
            self._gpu_freq_paths = sorted(freq_candidates)
            self._gpu_freq_path = self._gpu_freq_paths[0]

        # devfreq trans_stat for accurate GPU utilization on Orin.
        # The load file is a cached point-in-time snapshot that misses bursty
        # workloads. trans_stat tracks cumulative time at each frequency,
        # allowing utilization to be derived from deltas between samples.
        self._trans_stat_path = None
        self._prev_trans_stat = None
        if self._gpu_load_path and self._gpu_freq_path:
            ts_path = os.path.join(
                os.path.dirname(self._gpu_freq_path), 'trans_stat')
            if os.path.exists(ts_path):
                self._trans_stat_path = ts_path
                self._prev_trans_stat = self._parse_trans_stat()

        # GPU temperature - find thermal zone for GPU
        self._gpu_temp_path = None
        thermal_zones = glob.glob('/sys/class/thermal/thermal_zone*/type')
        for tz in sorted(thermal_zones):
            try:
                with open(tz, 'r') as f:
                    zone_type = f.read().strip().lower()
                if 'gpu' in zone_type:
                    self._gpu_temp_path = os.path.join(
                        os.path.dirname(tz), 'temp')
                    break
            except (OSError, ValueError):
                continue

        # Power monitoring paths (INA3221 sensors)
        self._power_paths = self._find_power_paths()

        # EMC (memory controller) frequency
        self._emc_freq_path = None
        emc_candidates = glob.glob('/sys/kernel/debug/bpmp/debug/clk/emc/rate')
        emc_candidates += glob.glob('/sys/devices/platform/*/devfreq/*/cur_freq')
        for candidate in emc_candidates:
            if 'emc' in candidate.lower():
                self._emc_freq_path = candidate
                break

        # EMC utilization (memory controller activity)
        self._emc_util_path = None
        emc_util_candidates = [
            '/sys/kernel/actmon_avg_activity/mc_all',
            '/sys/devices/platform/actmon_avg_activity/mc_all',
        ]
        emc_util_candidates += glob.glob(
            '/sys/devices/platform/*/actmon_avg_activity/mc_all')
        for candidate in emc_util_candidates:
            if os.path.exists(candidate):
                self._emc_util_path = candidate
                break

        # Theoretical max memory bandwidth by platform
        self._mem_bw_max_gbps = 204.8 if variant == 'jetson_orin' else 273.0

    def _parse_trans_stat(self):
        """Parse devfreq trans_stat into {freq_hz: time_ms} dict."""
        if not self._trans_stat_path:
            return None
        try:
            with open(self._trans_stat_path, 'r') as f:
                lines = f.readlines()
        except (OSError, ValueError):
            return None
        result = {}
        for line in lines:
            line = line.strip().lstrip('*').strip()
            # Lines: "306000000:  0  0  0  ... 1638884"
            # Last column is total time_ms at this frequency
            if ':' not in line or 'From' in line or 'Total' in line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                freq = int(parts[0].rstrip(':'))
                time_ms = int(parts[-1])
                result[freq] = time_ms
            except (ValueError, IndexError):
                continue
        return result if result else None

    def _query_nvml(self):
        """Query GPU utilization via NVML (fallback for Thor)."""
        metrics = {}
        if not self._nvml_handle:
            return metrics
        try:
            import pynvml
            util = pynvml.nvmlDeviceGetUtilizationRates(self._nvml_handle)
            metrics['gpu_util'] = float(util.gpu)
            metrics['gpu_mem_util'] = float(util.memory)
        except Exception:
            pass
        return metrics

    def _find_power_paths(self):
        """Find INA3221 or other power monitoring sysfs paths.

        Returns a dict of {label: path} for power*_input files,
        or a list of (label, voltage_path, current_path) tuples if
        only voltage/current are available (e.g. Orin INA3221).
        """
        power_paths = {}

        # Try hwmon-based power readings (common on newer Jetson BSPs)
        for hwmon_dir in sorted(glob.glob('/sys/class/hwmon/hwmon*')):
            name_path = os.path.join(hwmon_dir, 'name')
            try:
                with open(name_path, 'r') as f:
                    name = f.read().strip()
            except (OSError, ValueError):
                continue
            if 'ina' in name.lower() or 'power' in name.lower():
                # Look for power inputs
                for power_file in sorted(glob.glob(
                        os.path.join(hwmon_dir, 'power*_input'))):
                    label_file = power_file.replace('_input', '_label')
                    label = 'unknown'
                    try:
                        with open(label_file, 'r') as f:
                            label = f.read().strip()
                    except (OSError, ValueError):
                        pass
                    # Some sensors (e.g. INA238 on Thor) have a device-level
                    # label file instead of per-channel power*_label
                    if label == 'unknown':
                        device_label = os.path.join(hwmon_dir, 'label')
                        try:
                            with open(device_label, 'r') as f:
                                label = f.read().strip()
                        except (OSError, ValueError):
                            pass
                    power_paths[label] = power_file

        # Fallback: INA3221 via i2c
        if not power_paths:
            for power_file in sorted(glob.glob(
                    '/sys/bus/i2c/drivers/ina3221/*/hwmon/hwmon*/power*_input')):
                label_file = power_file.replace('_input', '_label')
                label = 'unknown'
                try:
                    with open(label_file, 'r') as f:
                        label = f.read().strip()
                except (OSError, ValueError):
                    pass
                power_paths[label] = power_file

        # Also collect voltage x current pairs for per-rail breakdown
        # (e.g. Orin INA3221 without power*_input, or Thor INA3221
        # alongside a separate INA238 total power sensor)
        self._power_vi_pairs = []
        for hwmon_dir in sorted(glob.glob('/sys/class/hwmon/hwmon*')):
            name_path = os.path.join(hwmon_dir, 'name')
            try:
                with open(name_path, 'r') as f:
                    name = f.read().strip()
            except (OSError, ValueError):
                continue
            if 'ina' not in name.lower():
                continue
            # INA3221 has 3 channels: in1/curr1, in2/curr2, in3/curr3
            for ch in range(1, 4):
                v_path = os.path.join(hwmon_dir, f'in{ch}_input')
                i_path = os.path.join(hwmon_dir, f'curr{ch}_input')
                label_path = os.path.join(hwmon_dir, f'in{ch}_label')
                if not (os.path.exists(v_path) and os.path.exists(i_path)):
                    continue
                label = 'unknown'
                try:
                    with open(label_path, 'r') as f:
                        label = f.read().strip()
                except (OSError, ValueError):
                    pass
                if label == 'unknown':
                    continue
                self._power_vi_pairs.append((label, v_path, i_path))

        return power_paths

    def collect(self):
        metrics = {}

        # GPU utilization
        if self._gpu_load_path:
            if self._trans_stat_path:
                # Derive utilization from devfreq trans_stat (cumulative time
                # at each frequency). The sysfs load file is a cached snapshot
                # that misses bursty sub-ms workloads; trans_stat is immune.
                curr = self._parse_trans_stat()
                if curr and self._prev_trans_stat:
                    idle_freq = min(curr.keys())
                    total_delta = 0
                    active_delta = 0
                    weighted_freq = 0
                    for freq, t in curr.items():
                        dt = t - self._prev_trans_stat.get(freq, 0)
                        if dt > 0:
                            total_delta += dt
                            if freq != idle_freq:
                                active_delta += dt
                            weighted_freq += freq * dt
                    if total_delta > 0:
                        metrics['gpu_util'] = round(
                            active_delta / total_delta * 100, 1)
                        metrics['gpu_clock_mhz'] = round(
                            weighted_freq / total_delta / 1_000_000, 1)
                    else:
                        # No transitions — GPU fully idle at lowest freq
                        metrics['gpu_util'] = 0.0
                        metrics['gpu_clock_mhz'] = round(
                            idle_freq / 1_000_000, 1)
                self._prev_trans_stat = curr
            # Fallback to instantaneous load file if trans_stat unavailable
            if 'gpu_util' not in metrics:
                val = self._read_sysfs(self._gpu_load_path)
                if val is not None:
                    metrics['gpu_util'] = round(val / 10.0, 1)
        elif self._nvml_handle:
            metrics.update(self._query_nvml())

        # GPU frequency (in Hz, convert to MHz)
        # Thor has dual clock domains (gpc + nvd), report all found
        if 'gpu_clock_mhz' not in metrics and self._gpu_freq_path:
            val = self._read_sysfs(self._gpu_freq_path)
            if val is not None:
                metrics['gpu_clock_mhz'] = round(val / 1_000_000, 1)
        if len(self._gpu_freq_paths) > 1:
            for i, path in enumerate(self._gpu_freq_paths[1:], 1):
                val = self._read_sysfs(path)
                if val is not None:
                    metrics[f'gpu_clock_{i}_mhz'] = round(val / 1_000_000, 1)

        # GPU temperature (in millidegrees C)
        if self._gpu_temp_path:
            val = self._read_sysfs(self._gpu_temp_path)
            if val is not None:
                metrics['gpu_temp'] = round(val / 1000.0, 1)

        # Power readings
        total_power_mw = 0
        has_power = False
        if self._power_paths:
            # Direct power*_input files (e.g. Thor INA238)
            # hwmon power*_input values are in microwatts (uW)
            for label, path in self._power_paths.items():
                val = self._read_sysfs(path)
                if val is not None:
                    val_mw = val / 1000.0
                    key = f'power_{label.lower().replace(" ", "_")}_mw'
                    metrics[key] = round(val_mw, 1)
                    if any(kw in label.lower() for kw in ['total', 'vdd', 'sys', 'vin', 'unknown']):
                        total_power_mw += val_mw
                        has_power = True
        if hasattr(self, '_power_vi_pairs') and self._power_vi_pairs:
            # Compute power from voltage x current (e.g. Orin INA3221)
            # Voltage in mV, current in mA -> power in mW = (mV * mA) / 1000
            # When direct power readings already provide board total (e.g. Thor
            # INA238), only log per-rail breakdown without double-counting.
            vi_counts_toward_total = not has_power
            for label, v_path, i_path in self._power_vi_pairs:
                voltage = self._read_sysfs(v_path)
                current = self._read_sysfs(i_path)
                if voltage is not None and current is not None:
                    power_mw = round(voltage * current / 1000.0, 1)
                    key = f'power_{label.lower().replace(" ", "_")}_mw'
                    metrics[key] = power_mw
                    if vi_counts_toward_total and any(
                            kw in label.lower()
                            for kw in ['total', 'vdd', 'sys', 'vin']):
                        total_power_mw += power_mw
                        has_power = True
        if has_power:
            metrics['board_power_w'] = round(total_power_mw / 1000.0, 2)

        # EMC frequency
        if self._emc_freq_path:
            val = self._read_sysfs(self._emc_freq_path)
            if val is not None:
                metrics['emc_freq_mhz'] = round(val / 1_000_000, 1)

        # Memory controller utilization and estimated bandwidth
        if self._emc_util_path:
            val = self._read_sysfs(self._emc_util_path)
            if val is not None:
                # Value is 0-1000, divide by 10 for percentage
                mem_busy = round(val / 10.0, 1)
                metrics['mem_busy_percent'] = mem_busy
                metrics['mem_bandwidth_gbps'] = round(
                    (mem_busy / 100.0) * self._mem_bw_max_gbps, 2)

        return metrics


if __name__ == '__main__':
    print(detect_platform())

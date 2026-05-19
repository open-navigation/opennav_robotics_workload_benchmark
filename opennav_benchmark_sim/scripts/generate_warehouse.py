#!/usr/bin/env python3
"""
Generate benchmark_warehouse.sdf.xacro procedurally.

Each zone is defined by a config dict with parametric values (shelf type,
spacing, start position, bounds, etc.).  Edit the ZONE / WAREHOUSE configs
at the top, then run:

    python3 generate_warehouse.py > ../worlds/benchmark_warehouse.sdf.xacro

Orientation convention (all shelves run E-W, long axis in X):
  - shelf      model default: ~3.5 m X, ~1.0 m Y  -> yaw = 0 keeps E-W
  - shelf_big  model default: ~7.5 m X, ~1.2 m Y  -> yaw = 0 keeps E-W

Big-shelf zones use back-to-back pairs: two shelves touching at the back,
then an aisle, then the next pair.  This is how real warehouse racking works.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass, field

# ──────────────────────────────────────────────────────────────────────
# RANDOMISATION
# ──────────────────────────────────────────────────────────────────────

RANDOM_SEED = 42
MAX_PALLET_YAW_DEG = 10      # +/- degrees for pallet orientation jitter
MAX_PALLET_XY_OFFSET = 0.25  # +/- metres for pallet position jitter

_rng = random.Random(RANDOM_SEED)


def random_yaw() -> float:
    """Return a random yaw in radians within +/- MAX_PALLET_YAW_DEG."""
    max_rad = math.radians(MAX_PALLET_YAW_DEG)
    return round(_rng.uniform(-max_rad, max_rad), 4)


def random_xy_offset() -> tuple[float, float]:
    """Return a random (dx, dy) offset within +/- MAX_PALLET_XY_OFFSET."""
    dx = round(_rng.uniform(-MAX_PALLET_XY_OFFSET, MAX_PALLET_XY_OFFSET), 4)
    dy = round(_rng.uniform(-MAX_PALLET_XY_OFFSET, MAX_PALLET_XY_OFFSET), 4)
    return dx, dy


# ──────────────────────────────────────────────────────────────────────
# WAREHOUSE-LEVEL PARAMETERS
# ──────────────────────────────────────────────────────────────────────

WAREHOUSE_X = 128          # metres, total E-W (extra 1m for west-wall clearance)
WAREHOUSE_Y = 140          # metres, total N-S
WALL_HEIGHT = 10.0         # metres

# Offset applied to all non-wall / non-ground assets to create room along
# the west wall
ASSET_X_OFFSET = 2.0

# N-S travel corridor / main alleyway (no shelves placed inside)
CORRIDOR_X_MIN = -3.0 + ASSET_X_OFFSET
CORRIDOR_X_MAX =  3.0 + ASSET_X_OFFSET

# Dock doors on the south wall
DOCK_DOOR_WIDTH = 4.0
DOCK_DOOR_CENTERS = [-50, -38, -26, -14, -2, 10, 22, 34]

# Inbound staging pallet clusters — moved close to dock doors
INBOUND_STAGING = {
    'cluster_centers_x': [-60, -43, -27, -10, 7],
    'cols_per_cluster': 3,        # pallets wide (E-W)
    'rows_per_cluster': 7,        # pallets deep (N-S)
    'col_spacing': 1.5,           # E-W spacing between pallets
    'row_spacing': 1.2,           # N-S spacing between pallets
    'y_start': -56.0,             # first row Y (close to dock doors at y=-70)
}

# Support columns on a grid (avoid corridors)
INTERIOR_COLUMNS = [
    (-40, -40), (-40, -23), (-40, 15), (-40, 40),
    (-20, -40), (-20, -23), (-20, 15), (-20, 40),
    ( 20, -40), ( 20, -23), ( 20, 15), ( 20, 40),
    ( 40, -40), ( 40, -23), ( 40, 15),
]

# Block-stack pallet clusters near small-shelf zones.
# Each tuple: (name_prefix, center_x, center_y, cols_x, rows_y, spacing)
# Pallets are stacked 2-4 tall (shortest on outside, tallest in center).
PALLET_STACK_HEIGHT = 1.2     # metres per pallet level
PALLET_STACKS = [
    # East of Zone C (open floor where office used to be)
    ('ps_a', 37, 33, 5, 7, 1.3),
    ('ps_b', 37, 42, 5, 7, 1.3),
    ('ps_c', 48, 33, 5, 7, 1.3),
    ('ps_d', 48, 42, 5, 7, 1.3),
    # Loading dock area along right (east) wall, below shelves
    ('ps_dock', 48, -60, 14, 10, 1.3),
]


# ──────────────────────────────────────────────────────────────────────
# SHELF ZONE CONFIGURATION
# ──────────────────────────────────────────────────────────────────────

def make_paired_rows(y_start: float, n_pairs: int,
                     pair_gap: float, aisle: float) -> list[float]:
    """Generate Y positions for back-to-back shelf pairs.

    Each pair is two rows separated by pair_gap (shelf depth, touching).
    Pairs are separated by the aisle width.

    Args:
        y_start:  Y of the first shelf in the first pair.
        n_pairs:  Number of back-to-back pairs.
        pair_gap: Center-to-center distance within a pair (= shelf depth).
        aisle:    Clear aisle between adjacent pairs.
    """
    rows = []
    step = pair_gap + aisle + pair_gap  # first-shelf-of-pair to first-shelf-of-next
    # Actually: shelf edges: pair occupies [y, y+pair_gap+depth... no.
    # Pair: shelf_a at y (edges y-d/2 to y+d/2), shelf_b at y+pair_gap
    #   (edges y+pair_gap-d/2 to y+pair_gap+d/2)
    # Outer edge of pair = y + pair_gap + d/2, where d = pair_gap (since pair_gap == depth)
    # Next pair first shelf inner edge = outer_edge + aisle
    # = y + pair_gap + pair_gap/2 + aisle
    # Next pair first shelf center = y + pair_gap + pair_gap/2 + aisle + pair_gap/2
    # = y + 2*pair_gap + aisle
    step = 2 * pair_gap + aisle
    for i in range(n_pairs):
        y0 = y_start + i * step
        rows.append(round(y0, 2))
        rows.append(round(y0 + pair_gap, 2))
    return rows


@dataclass
class ShelfZone:
    """Parametric racking zone."""
    name: str
    label: str
    shelf_type: str              # "big" or "small"

    shelf_length_x: float        # long axis (E-W), metres
    shelf_depth_y: float         # short axis (N-S), metres

    row_y_positions: list[float]
    ctc_x: float                 # center-to-center in X between shelves in a row
    x_min: float
    x_max: float

    paired: bool = False         # True for back-to-back big-shelf zones

    def aisle_width(self) -> float:
        """Clear aisle between adjacent rows (or between pairs)."""
        if len(self.row_y_positions) < 2:
            return 0.0
        if self.paired and len(self.row_y_positions) >= 3:
            # Aisle is between row[1] (2nd shelf of pair 1) and row[2] (1st shelf of pair 2)
            dy = abs(self.row_y_positions[2] - self.row_y_positions[1])
        else:
            dy = abs(self.row_y_positions[1] - self.row_y_positions[0])
        return dy - self.shelf_depth_y

    def x_positions(self) -> list[float]:
        """All shelf-center X positions, respecting N-S corridor gap."""
        positions = []
        x = self.x_min + ASSET_X_OFFSET
        while x <= self.x_max + ASSET_X_OFFSET + 0.01:
            half = self.shelf_length_x / 2.0
            if (x + half) < CORRIDOR_X_MIN or (x - half) > CORRIDOR_X_MAX:
                positions.append(round(x, 2))
            x += self.ctc_x
        return positions


# --- Zone A: Bulk Storage (big shelves, back-to-back pairs) ---
# Pair gap = 1.2 m (shelf depth, back-to-back touching).
# Aisle between pairs = 2.0 m (30% reduction from original 2.8 m).
_za_y_south = make_paired_rows(y_start=-37.2, n_pairs=3, pair_gap=1.2, aisle=2.0)
_za_y_north = make_paired_rows(y_start=-22, n_pairs=4, pair_gap=1.2, aisle=2.0)

ZONE_A = ShelfZone(
    name='zone_a',
    label='ZONE A: BULK STORAGE (big shelves, back-to-back pairs, 2.0 m aisles)',
    shelf_type='big',
    shelf_length_x=7.5,
    shelf_depth_y=1.2,
    row_y_positions=_za_y_south + _za_y_north,
    ctc_x=8.0,
    x_min=-56,
    x_max=56,
    paired=True,
)

# --- Zone B-West: Standard (big shelves, back-to-back pairs) ---
# Aisle between pairs = 1.6 m (30% reduction from original 2.3 m).
_zbw_y = make_paired_rows(y_start=4, n_pairs=4, pair_gap=1.2, aisle=1.6)

ZONE_B_WEST = ShelfZone(
    name='zone_bw',
    label='ZONE B-WEST: STANDARD (big shelves, back-to-back pairs, 1.6 m aisles)',
    shelf_type='big',
    shelf_length_x=7.5,
    shelf_depth_y=1.2,
    row_y_positions=_zbw_y,
    ctc_x=8.0,
    x_min=-56,
    x_max=-6,
    paired=True,
)

# --- Zone B-East: Narrow (small shelves, tight aisles) ---
ZONE_B_EAST = ShelfZone(
    name='zone_be',
    label='ZONE B-EAST: NARROW (small shelves, 3.0 m c-t-c, ~2.0 m aisles)',
    shelf_type='small',
    shelf_length_x=3.5,
    shelf_depth_y=1.0,
    row_y_positions=[8, 11, 14, 17, 20, 23],
    ctc_x=4.0,
    x_min=5,
    x_max=53,
)

# --- Zone C: Forward Pick (small shelves, most confined) ---
ZONE_C = ShelfZone(
    name='zone_c',
    label='ZONE C: FORWARD PICK (small shelves, 3.0 m c-t-c, ~2.0 m aisles)',
    shelf_type='small',
    shelf_length_x=3.5,
    shelf_depth_y=1.0,
    row_y_positions=[30, 33, 36, 39, 42, 45],
    ctc_x=4.0,
    x_min=-55,
    x_max=29,
)

# --- Zone D: Back Storage (big shelves rotated N-S, back-to-back pairs in X) ---
# Perpendicular to current big shelves, parallel to small shelves.
# Rotated shelf_big: 1.2m X (depth) x 7.5m Y (length).
# Back-to-back pairs arranged in X, shelves spaced in Y.
ZONE_D = {
    'name': 'zone_d',
    'label': 'ZONE D: BACK STORAGE (big shelves N-S, back-to-back pairs, 2.0 m aisles)',
    'shelf_depth_x': 1.2,       # shelf width in X after rotation
    'shelf_length_y': 7.5,      # shelf length in Y after rotation
    'pair_gap': 1.2,            # center-to-center within a pair (X direction)
    'aisle': 2.0,               # clear aisle between pairs (X direction)
    'x_min': -46,
    'x_max': 46,
    'y_positions': [51, 62],    # shelf centers in Y (~4m clear E-W break between rows)
    'ctc_y': 11.0,              # center-to-center in Y
}

ALL_ZONES = [ZONE_A, ZONE_B_WEST, ZONE_B_EAST, ZONE_C]


# ──────────────────────────────────────────────────────────────────────
# SDF GENERATION HELPERS
# ──────────────────────────────────────────────────────────────────────

class SDFWriter:
    """Accumulates SDF lines and writes them out."""

    def __init__(self):
        self._lines: list[str] = []
        self._stats: dict[str, int] = {}

    def w(self, line: str = ''):
        self._lines.append(line)

    def stat(self, key: str, count: int):
        self._stats[key] = self._stats.get(key, 0) + count

    def dump(self, fh=sys.stdout):
        fh.write('\n'.join(self._lines) + '\n')

    def dump_stats(self, fh=sys.stderr):
        fh.write('\n=== SUMMARY ===\n')
        for k, v in self._stats.items():
            fh.write(f'  {k}: {v}\n')
        total = sum(v for k, v in self._stats.items() if 'shelves' in k.lower())
        fh.write(f'  TOTAL SHELVES: {total}\n')


# ──────────────────────────────────────────────────────────────────────
# SDF BUILDING BLOCKS
# ──────────────────────────────────────────────────────────────────────

def write_header(s: SDFWriter):
    s.w('<?xml version="1.0"?>')
    s.w('<sdf version="1.7" xmlns:xacro="http://www.ros.org/wiki/xacro">')
    s.w('  <xacro:arg name="headless" default="false"/>')
    s.w('')
    s.w('  <world name="benchmark_warehouse">')
    s.w('')
    s.w('    <!-- Physics -->')
    s.w('    <physics name="5ms" type="bullet">')
    s.w('      <max_step_size>0.005</max_step_size>')
    s.w('      <real_time_update_rate>500.0</real_time_update_rate>')
    s.w('      <real_time_factor>1.0</real_time_factor>')
    s.w('    </physics>')
    s.w('')
    s.w('    <!-- Plugins -->')
    s.w('    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>')
    s.w('    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>')
    s.w('    <xacro:unless value="$(arg headless)">')
    s.w('      <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>')
    s.w('    </xacro:unless>')
    s.w('    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">')
    s.w('      <render_engine>ogre2</render_engine>')
    s.w('    </plugin>')
    s.w('    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>')
    s.w('')
    s.w('    <!-- Scene -->')
    s.w('    <scene>')
    s.w('      <ambient>0.8 0.8 0.8 1</ambient>')
    s.w('      <background>0.3 0.7 0.9 1</background>')
    s.w('      <shadows>0</shadows>')
    s.w('      <grid>false</grid>')
    s.w('    </scene>')
    s.w('')
    s.w('    <!-- Lighting -->')
    s.w('    <light type="directional" name="sun">')
    s.w('      <cast_shadows>false</cast_shadows>')
    s.w('      <pose>0 0 50 0 0 0</pose>')
    s.w('      <diffuse>0.9 0.9 0.9 1</diffuse>')
    s.w('      <specular>0.3 0.3 0.3 1</specular>')
    s.w('      <attenuation>')
    s.w('        <range>1000</range>')
    s.w('        <constant>0.9</constant>')
    s.w('        <linear>0.001</linear>')
    s.w('        <quadratic>0.0001</quadratic>')
    s.w('      </attenuation>')
    s.w('      <direction>-0.3 0.2 -1.0</direction>')
    s.w('    </light>')
    s.w('')


def write_ground_plane(s: SDFWriter):
    wx, wy = WAREHOUSE_X, WAREHOUSE_Y
    s.w(f'    <!-- Ground plane ({wx}m x {wy}m) -->')
    s.w('    <model name="ground_plane">')
    s.w('      <static>true</static>')
    s.w('      <link name="link">')
    s.w('        <collision name="collision">')
    s.w(f'          <geometry><plane><normal>0 0 1</normal><size>{wx} {wy}</size></plane></geometry>')
    s.w('        </collision>')
    s.w('        <visual name="visual">')
    s.w(f'          <geometry><plane><normal>0 0 1</normal><size>{wx} {wy}</size></plane></geometry>')
    s.w('          <material>')
    s.w('            <ambient>0.55 0.55 0.53 1</ambient>')
    s.w('            <diffuse>0.55 0.55 0.53 1</diffuse>')
    s.w('            <specular>0.1 0.1 0.1 1</specular>')
    s.w('          </material>')
    s.w('        </visual>')
    s.w('      </link>')
    s.w('      <pose>0 0 0 0 0 0</pose>')
    s.w('    </model>')
    s.w('')




def write_macros(s: SDFWriter):
    h = WALL_HEIGHT
    lower_h = 2.5
    upper_h = h - lower_h

    s.w('    <!-- ============================================================ -->')
    s.w('    <!-- MACROS                                                        -->')
    s.w('    <!-- ============================================================ -->')
    s.w('')

    # Brick wall
    s.w(f'    <!-- Brick perimeter wall ({h}m tall, two-tone red brick) -->')
    s.w('    <xacro:macro name="wall_segment" params="name x y yaw length">')
    s.w('      <model name="wall_${name}">')
    s.w('        <static>true</static>')
    s.w('        <pose>${x} ${y} 0 0 0 ${yaw}</pose>')
    s.w('        <link name="link">')
    s.w('          <visual name="lower">')
    s.w(f'            <pose>0 0 {lower_h/2} 0 0 0</pose>')
    s.w(f'            <geometry><box><size>${{length}} 0.3 {lower_h}</size></box></geometry>')
    s.w('            <material>')
    s.w('              <ambient>0.50 0.18 0.08 1</ambient>')
    s.w('              <diffuse>0.50 0.18 0.08 1</diffuse>')
    s.w('              <specular>0.05 0.05 0.05 1</specular>')
    s.w('            </material>')
    s.w('          </visual>')
    s.w('          <visual name="upper">')
    s.w(f'            <pose>0 0 {lower_h + upper_h/2} 0 0 0</pose>')
    s.w(f'            <geometry><box><size>${{length}} 0.3 {upper_h}</size></box></geometry>')
    s.w('            <material>')
    s.w('              <ambient>0.65 0.28 0.12 1</ambient>')
    s.w('              <diffuse>0.65 0.28 0.12 1</diffuse>')
    s.w('              <specular>0.05 0.05 0.05 1</specular>')
    s.w('            </material>')
    s.w('          </visual>')
    s.w('          <collision name="collision">')
    s.w(f'            <pose>0 0 {h/2} 0 0 0</pose>')
    s.w(f'            <geometry><box><size>${{length}} 0.3 {h}</size></box></geometry>')
    s.w('          </collision>')
    s.w('        </link>')
    s.w('      </model>')
    s.w('    </xacro:macro>')
    s.w('')

    # Dock door
    s.w('    <!-- Roll-up dock door (4m wide x 5m tall, brick above) -->')
    s.w('    <xacro:macro name="dock_door" params="name x y yaw">')
    s.w('      <model name="door_${name}">')
    s.w('        <static>true</static>')
    s.w('        <pose>${x} ${y} 0 0 0 ${yaw}</pose>')
    s.w('        <link name="link">')
    s.w('          <visual name="door_panel">')
    s.w('            <pose>0 0 2.5 0 0 0</pose>')
    s.w(f'            <geometry><box><size>{DOCK_DOOR_WIDTH} 0.15 5.0</size></box></geometry>')
    s.w('            <material>')
    s.w('              <ambient>0.55 0.56 0.58 1</ambient>')
    s.w('              <diffuse>0.55 0.56 0.58 1</diffuse>')
    s.w('              <specular>0.4 0.4 0.4 1</specular>')
    s.w('            </material>')
    s.w('          </visual>')
    s.w('          <visual name="above_door">')
    s.w(f'            <pose>0 0 7.5 0 0 0</pose>')
    s.w(f'            <geometry><box><size>{DOCK_DOOR_WIDTH} 0.3 5.0</size></box></geometry>')
    s.w('            <material>')
    s.w('              <ambient>0.65 0.28 0.12 1</ambient>')
    s.w('              <diffuse>0.65 0.28 0.12 1</diffuse>')
    s.w('              <specular>0.05 0.05 0.05 1</specular>')
    s.w('            </material>')
    s.w('          </visual>')
    s.w('          <collision name="collision">')
    s.w('            <pose>0 0 2.5 0 0 0</pose>')
    s.w(f'            <geometry><box><size>{DOCK_DOOR_WIDTH} 0.15 5.0</size></box></geometry>')
    s.w('          </collision>')
    s.w('        </link>')
    s.w('      </model>')
    s.w('    </xacro:macro>')
    s.w('')

    # Support column
    s.w(f'    <!-- Support column ({h}m tall) -->')
    s.w('    <xacro:macro name="support_column" params="name x y">')
    s.w('      <model name="col_${name}">')
    s.w('        <static>true</static>')
    s.w(f'        <pose>${{x}} ${{y}} {h/2} 0 0 0</pose>')
    s.w('        <link name="link">')
    s.w('          <visual name="visual">')
    s.w(f'            <geometry><box><size>0.4 0.4 {h}</size></box></geometry>')
    s.w('            <material>')
    s.w('              <ambient>0.55 0.52 0.50 1</ambient>')
    s.w('              <diffuse>0.55 0.52 0.50 1</diffuse>')
    s.w('              <specular>0.2 0.2 0.2 1</specular>')
    s.w('            </material>')
    s.w('          </visual>')
    s.w('          <collision name="collision">')
    s.w(f'            <geometry><box><size>0.4 0.4 {h}</size></box></geometry>')
    s.w('          </collision>')
    s.w('        </link>')
    s.w('      </model>')
    s.w('    </xacro:macro>')
    s.w('')

    # Shelf macros — both E-W at yaw=0
    s.w('    <!-- Shelf macros: ALL running E-W (long axis in X), yaw=0 -->')
    s.w('    <!-- shelf default: 3.5m X x 1m Y -->')
    s.w('    <xacro:macro name="small_shelf" params="name x y">')
    s.w('      <include>')
    s.w('        <uri>shelf</uri>')
    s.w('        <name>${name}</name>')
    s.w('        <pose>${x} ${y} 0 0 0 0</pose>')
    s.w('        <static>true</static>')
    s.w('      </include>')
    s.w('    </xacro:macro>')
    s.w('')
    s.w('    <!-- shelf_big default: 7.5m X x 1.2m Y -->')
    s.w('    <xacro:macro name="big_shelf" params="name x y">')
    s.w('      <include>')
    s.w('        <uri>shelf_big</uri>')
    s.w('        <name>${name}</name>')
    s.w('        <pose>${x} ${y} 0 0 0 0</pose>')
    s.w('        <static>true</static>')
    s.w('      </include>')
    s.w('    </xacro:macro>')
    s.w('')
    s.w('    <!-- shelf_big rotated N-S: 1.2m X x 7.5m Y -->')
    s.w('    <xacro:macro name="big_shelf_ns" params="name x y">')
    s.w('      <include>')
    s.w('        <uri>shelf_big</uri>')
    s.w('        <name>${name}</name>')
    s.w('        <pose>${x} ${y} 0 0 0 1.5708</pose>')
    s.w('        <static>true</static>')
    s.w('      </include>')
    s.w('    </xacro:macro>')
    s.w('')

    # Pallet macro (accepts z for stacking)
    s.w('    <!-- Pallet macro -->')
    s.w('    <xacro:macro name="pallet" params="name x y z yaw">')
    s.w('      <include>')
    s.w('        <uri>pallet_box_mobile</uri>')
    s.w('        <name>${name}</name>')
    s.w('        <pose>${x} ${y} ${z} 0 0 ${yaw}</pose>')
    s.w('        <static>true</static>')
    s.w('      </include>')
    s.w('    </xacro:macro>')
    s.w('')


def write_perimeter_walls(s: SDFWriter):
    hx = WAREHOUSE_X / 2.0
    hy = WAREHOUSE_Y / 2.0

    s.w('    <!-- ============================================================ -->')
    s.w(f'    <!-- PERIMETER WALLS ({WAREHOUSE_X}m x {WAREHOUSE_Y}m, {WALL_HEIGHT}m tall brick) -->')
    s.w('    <!-- ============================================================ -->')
    s.w('')
    s.w(f'    <xacro:wall_segment name="north" x="0" y="{hy}" yaw="0" length="{WAREHOUSE_X}"/>')
    s.w(f'    <xacro:wall_segment name="east" x="{hx}" y="0" yaw="1.5708" length="{WAREHOUSE_Y}"/>')
    s.w(f'    <xacro:wall_segment name="west" x="-{hx}" y="0" yaw="1.5708" length="{WAREHOUSE_Y}"/>')
    s.w('')

    # South wall split for dock doors
    dw = DOCK_DOOR_WIDTH
    segs = [(-hx, DOCK_DOOR_CENTERS[0] - dw / 2)]
    for i in range(len(DOCK_DOOR_CENTERS) - 1):
        segs.append((DOCK_DOOR_CENTERS[i] + dw / 2, DOCK_DOOR_CENTERS[i + 1] - dw / 2))
    segs.append((DOCK_DOOR_CENTERS[-1] + dw / 2, hx))

    s.w('    <!-- South wall segments (between dock doors) -->')
    for i, (x1, x2) in enumerate(segs):
        cx = (x1 + x2) / 2.0
        length = x2 - x1
        s.w(f'    <xacro:wall_segment name="south_{i+1}" x="{cx}" y="-{hy}" yaw="0" length="{length}"/>')
    s.w('')

    s.w('    <!-- Roll-up dock doors -->')
    for i, dx in enumerate(DOCK_DOOR_CENTERS):
        s.w(f'    <xacro:dock_door name="dock{i+1}" x="{dx}" y="-{hy}" yaw="0"/>')
    s.w('')


def write_columns(s: SDFWriter):
    hx = WAREHOUSE_X / 2.0
    hy = WAREHOUSE_Y / 2.0

    s.w('    <!-- ============================================================ -->')
    s.w('    <!-- SUPPORT COLUMNS                                               -->')
    s.w('    <!-- ============================================================ -->')
    s.w('')

    idx = 0
    for x in range(-45, 46, 15):
        s.w(f'    <xacro:support_column name="n{idx}" x="{x}" y="{hy}"/>')
        idx += 1
    for x in [-56, -44, -32, -20, -8, 4, 16]:
        s.w(f'    <xacro:support_column name="s{idx}" x="{x}" y="-{hy}"/>')
        idx += 1
    for y in range(-60, 61, 20):
        s.w(f'    <xacro:support_column name="e{idx}" x="{hx}" y="{y}"/>')
        idx += 1
    for y in range(-60, 61, 20):
        s.w(f'    <xacro:support_column name="w{idx}" x="-{hx}" y="{y}"/>')
        idx += 1
    for (x, y) in INTERIOR_COLUMNS:
        s.w(f'    <xacro:support_column name="int_{idx}" x="{x + ASSET_X_OFFSET}" y="{y}"/>')
        idx += 1
    s.w('')


def write_shelf_zone(s: SDFWriter, zone: ShelfZone):
    """Generate all shelf placements for a single zone."""
    macro = 'big_shelf' if zone.shelf_type == 'big' else 'small_shelf'
    x_positions = zone.x_positions()
    y_positions = zone.row_y_positions

    s.w('    <!-- ============================================================ -->')
    s.w(f'    <!-- {zone.label} -->')
    s.w(f'    <!-- {len(y_positions)} rows x {len(x_positions)} per row, '
        f'aisle ~{zone.aisle_width():.1f}m -->')
    s.w('    <!-- ============================================================ -->')
    s.w('')

    count = 0
    for ri, ry in enumerate(y_positions, 1):
        for ci, rx in enumerate(x_positions, 1):
            s.w(f'    <xacro:{macro} name="{zone.name}_r{ri}_{ci}" x="{rx}" y="{ry}"/>')
            count += 1

    label = f'{zone.name} shelves ({zone.shelf_type})'
    s.w(f'    <!-- {label}: {count} -->')
    s.w('')
    s.stat(label, count)


def write_zone_d(s: SDFWriter):
    """Generate Zone D: rotated big shelves (N-S) in back-to-back pairs along X."""
    d = ZONE_D
    pair_gap = d['pair_gap']
    aisle = d['aisle']
    depth = d['shelf_depth_x']
    step = 2 * pair_gap + aisle  # center-to-center between pairs

    # E-W cross-aisle breaks: skip pairs whose center falls in these X bands
    # Gaps in X where pairs are skipped: center (wide entrance from N-S corridor)
    # and two lateral breaks for E-W access
    cross_aisle_breaks = [(-34, -22), (-12, 8), (22, 34)]

    # Generate X positions for back-to-back pairs, respecting N-S corridor
    # and cross-aisle breaks.  Apply ASSET_X_OFFSET to shift away from west wall.
    cross_aisle_breaks = [(lo + ASSET_X_OFFSET, hi + ASSET_X_OFFSET)
                          for lo, hi in cross_aisle_breaks]
    x_positions = []
    x = d['x_min'] + ASSET_X_OFFSET
    while x <= d['x_max'] + ASSET_X_OFFSET + 0.01:
        x2 = x + pair_gap  # second shelf in pair
        half = depth / 2.0
        mid = (x + x2) / 2.0
        # Check neither shelf in the pair overlaps the corridor
        s1_ok = (x + half) < CORRIDOR_X_MIN or (x - half) > CORRIDOR_X_MAX
        s2_ok = (x2 + half) < CORRIDOR_X_MIN or (x2 - half) > CORRIDOR_X_MAX
        # Check pair doesn't fall in a cross-aisle break
        in_break = any(lo <= mid <= hi for lo, hi in cross_aisle_breaks)
        if s1_ok and s2_ok and not in_break:
            x_positions.append((round(x, 2), round(x2, 2)))
        x += step

    y_positions = d['y_positions']
    n_pairs = len(x_positions)
    n_y = len(y_positions)

    s.w('    <!-- ============================================================ -->')
    s.w(f'    <!-- {d["label"]} -->')
    s.w(f'    <!-- {n_pairs} back-to-back pairs x {n_y} deep, aisle {aisle}m -->')
    s.w('    <!-- ============================================================ -->')
    s.w('')

    count = 0
    for pi, (x1, x2) in enumerate(x_positions, 1):
        for yi, yc in enumerate(y_positions, 1):
            s.w(f'    <xacro:big_shelf_ns name="{d["name"]}_p{pi}a_{yi}" x="{x1}" y="{yc}"/>')
            s.w(f'    <xacro:big_shelf_ns name="{d["name"]}_p{pi}b_{yi}" x="{x2}" y="{yc}"/>')
            count += 2

    label = f'{d["name"]} shelves (big, N-S)'
    s.w(f'    <!-- {label}: {count} -->')
    s.w('')
    s.stat(label, count)


def write_inbound_staging(s: SDFWriter):
    cfg = INBOUND_STAGING
    clusters = cfg['cluster_centers_x']
    cols = cfg['cols_per_cluster']
    rows = cfg['rows_per_cluster']
    col_sp = cfg['col_spacing']
    row_sp = cfg['row_spacing']
    y_start = cfg['y_start']

    s.w('    <!-- ============================================================ -->')
    s.w(f'    <!-- INBOUND STAGING ({len(clusters)} clusters, '
        f'{cols} wide x {rows} deep = {cols*rows} each) -->')
    s.w('    <!-- ============================================================ -->')
    s.w('')

    total = 0
    for ci, cx in enumerate(clusters, 1):
        s.w(f'    <!-- Cluster {ci} at x={cx} -->')
        col_offsets = [(c - (cols - 1) / 2.0) * col_sp for c in range(cols)]
        for ri in range(rows):
            ry = y_start - ri * row_sp
            for pi, xo in enumerate(col_offsets, 1):
                yaw = random_yaw()
                dx, dy = random_xy_offset()
                px = round(cx + xo + ASSET_X_OFFSET + dx, 2)
                py = round(ry + dy, 2)
                s.w(f'    <xacro:pallet name="pin_c{ci}_r{ri+1}_{pi}" '
                    f'x="{px}" y="{py}" z="0.01" yaw="{yaw}"/>')
                total += 1
        s.w('')

    s.w(f'    <!-- Inbound staging: {total} pallets -->')
    s.w('')
    s.stat('Inbound pallets', total)


def _stack_height(xi: int, yi: int, nx: int, ny: int) -> int:
    """Determine pallet stack height (2-4) based on distance from cluster edge.

    Edge positions always get the minimum (2).  Interior positions get a
    random height that increases toward the centre.
    """
    dist = min(xi, yi, nx - 1 - xi, ny - 1 - yi)
    if dist == 0:
        return 2
    elif dist == 1:
        return _rng.choice([2, 3])
    else:
        return _rng.choice([3, 4])


def write_pallet_stacks(s: SDFWriter):
    """Block-stack pallet clusters stacked 2-4 tall, shortest on outside."""
    s.w('    <!-- ============================================================ -->')
    s.w('    <!-- BLOCK-STACK PALLETS (2-4 tall, shortest on outside)           -->')
    s.w('    <!-- ============================================================ -->')
    s.w('')

    h = PALLET_STACK_HEIGHT
    total = 0
    for prefix, cx, cy, nx, ny, sp in PALLET_STACKS:
        s.w(f'    <!-- Stack {prefix} at ({cx}, {cy}), {nx}x{ny} -->')
        for xi in range(nx):
            for yi in range(ny):
                dx, dy = random_xy_offset()
                px = round(cx + (xi - (nx - 1) / 2.0) * sp + ASSET_X_OFFSET + dx, 2)
                py = round(cy + (yi - (ny - 1) / 2.0) * sp + dy, 2)
                n_levels = _stack_height(xi, yi, nx, ny)
                yaw = random_yaw()
                for lv in range(n_levels):
                    z = round(0.01 + lv * h, 2)
                    s.w(f'    <xacro:pallet name="{prefix}_{xi}_{yi}_L{lv+1}" '
                        f'x="{px}" y="{py}" z="{z}" yaw="{yaw}"/>')
                    total += 1
        s.w('')

    s.w(f'    <!-- Block-stack pallets: {total} models -->')
    s.w('')
    s.stat('Block-stack pallets', total)


def write_footer(s: SDFWriter):
    s.w('  </world>')
    s.w('</sdf>')


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    s = SDFWriter()

    write_header(s)
    write_ground_plane(s)
    write_macros(s)
    write_perimeter_walls(s)
    write_columns(s)

    for zone in ALL_ZONES:
        write_shelf_zone(s, zone)

    write_zone_d(s)
    write_inbound_staging(s)
    write_pallet_stacks(s)
    write_footer(s)

    s.dump(sys.stdout)
    s.dump_stats(sys.stderr)


if __name__ == '__main__':
    main()

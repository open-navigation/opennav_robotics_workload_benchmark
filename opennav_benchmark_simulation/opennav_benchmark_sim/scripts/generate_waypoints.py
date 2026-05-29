#!/usr/bin/env python3
"""
Generate aisle waypoints for the benchmark warehouse.

Reads zone geometry from generate_warehouse.py and distributes waypoints
along each aisle at configurable intervals, offset from the shelf face.

Usage:
    python3 generate_waypoints.py                        # default output path
    python3 generate_waypoints.py -o /custom/path.yaml   # custom output
"""

from __future__ import annotations

import argparse
import math
import os
import sys

import yaml

# Import zone configs from the warehouse generator (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_warehouse import (  # noqa: E402
    ASSET_X_OFFSET,
    CORRIDOR_X_MAX,
    CORRIDOR_X_MIN,
    INBOUND_STAGING,
    PALLET_STACKS,
    ZONE_A,
    ZONE_B_EAST,
    ZONE_B_WEST,
    ZONE_C,
    ZONE_D,
    ShelfZone,
)

# ── Configurable parameters ─────────────────────────────────────────
BIG_SHELF_WP_SPACING = 5.0       # metres between waypoints along big-shelf rows
SMALL_SHELF_WP_SPACING = 3.0     # metres between waypoints along small-shelf rows
BIG_SHELF_AISLE_OFFSET = 1.5     # metres from shelf center into aisle (big)
SMALL_SHELF_AISLE_OFFSET = 1.2   # metres from shelf center into aisle (small)
BIG_SHELF_LANE_OFFSET = 1.0      # metres from aisle center to each lane (big)
SMALL_SHELF_LANE_OFFSET = 0.5    # metres from aisle center to each lane (small)

CORRIDOR_MARGIN = 0.5  # extra clearance around the N-S corridor
PICKUP_CLEARANCE = 2.45  # metres from pallet cluster edge to pickup waypoint

# Actual shelf mesh dimensions (from shelf_big_movai.dae)
SHELF_LINK_X_OFFSET = -0.5       # link pose offset in all shelf models
BIG_SHELF_MESH_LENGTH = 18.06    # raw mesh long axis (runs N-S after π/2 rotation)
BIG_SHELF_MESH_WIDTH = 2.14      # raw mesh short axis (runs E-W after π/2 rotation)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_ew_waypoints(
    y: float, yaw: float, x_min: float, x_max: float, spacing: float,
) -> dict[str, dict]:
    """Distribute waypoints along X (E-W), splitting at the N-S corridor.

    Each side of the corridor gets an independent, evenly spaced
    distribution so that waypoints are properly centred within their
    respective shelf sections.
    """
    corr_lo = CORRIDOR_X_MIN - CORRIDOR_MARGIN
    corr_hi = CORRIDOR_X_MAX + CORRIDOR_MARGIN

    # Split into independent segments around the corridor.
    # Corridor-adjacent ends use the last shelf center (not edge)
    # so waypoints don't extend past shelves into the open corridor.
    west_end = corr_lo - spacing  # stop one spacing before corridor
    segments: list[tuple[float, float]] = []
    if x_min < corr_lo and x_max > corr_hi:
        segments.append((x_min, west_end))
        segments.append((corr_hi, x_max))
    elif x_max <= corr_lo or x_min >= corr_hi:
        segments.append((x_min, x_max))
    elif x_min < corr_lo:
        segments.append((x_min, west_end))
    elif x_max > corr_hi:
        segments.append((corr_hi, x_max))

    slots: dict[str, dict] = {}
    slot_idx = 1
    for seg_min, seg_max in segments:
        seg_len = seg_max - seg_min
        n = max(1, round(seg_len / spacing))
        actual_spacing = seg_len / n
        for i in range(n + 1):
            x = seg_min + i * actual_spacing
            slots[f'slot_{slot_idx}'] = {
                'x': round(x, 2),
                'y': round(y, 2),
                'yaw': round(yaw, 4),
            }
            slot_idx += 1
    return slots


def _make_ns_waypoints(
    x: float, yaw: float, y_min: float, y_max: float, spacing: float,
) -> dict[str, dict]:
    """Distribute waypoints along Y (N-S) for vertical aisles."""
    n = max(1, round((y_max - y_min) / spacing))
    actual_spacing = (y_max - y_min) / n

    slots: dict[str, dict] = {}
    slot_idx = 1
    for i in range(n + 1):
        y = y_min + i * actual_spacing
        slots[f'slot_{slot_idx}'] = {
            'x': round(x, 2),
            'y': round(y, 2),
            'yaw': round(yaw, 4),
        }
        slot_idx += 1
    return slots


def _ew_row_extents(zone: ShelfZone) -> tuple[float, float]:
    """X extent of the continuous shelf row (min edge to max edge).

    Accounts for the model link X offset so waypoints align with the
    actual shelf positions visible on the map.
    """
    x_positions = zone.x_positions()
    half = zone.shelf_length_x / 2.0
    return (min(x_positions) + SHELF_LINK_X_OFFSET - half,
            max(x_positions) + SHELF_LINK_X_OFFSET + half)


# ── Zone generators ─────────────────────────────────────────────────

def generate_waypoints_paired_ew(zone: ShelfZone) -> dict:
    """Generate aisle waypoints for big-shelf zones.

    The big-shelf mesh runs N-S on the map, so the navigable aisles are
    the vertical (N-S) gaps between adjacent shelf columns.  Each aisle
    gets two lanes (west and east side) with opposite-facing yaw to
    create directional lanes.  Includes outer aisles on the outside of
    the first/last columns and corridor-facing columns.
    """
    rows = zone.row_y_positions
    x_positions = zone.x_positions()
    spacing = BIG_SHELF_WP_SPACING
    lane_offset = BIG_SHELF_LANE_OFFSET
    col_half = BIG_SHELF_MESH_WIDTH / 2.0

    # Y extent: full length of actual shelf mesh
    y_min = min(rows) - BIG_SHELF_MESH_LENGTH / 2.0
    y_max = max(rows) + BIG_SHELF_MESH_LENGTH / 2.0

    # Actual column X centers (account for model link offset)
    cols = [x + SHELF_LINK_X_OFFSET for x in x_positions]

    # Split columns into groups separated by the corridor
    groups: list[list[float]] = [[cols[0]]]
    for i in range(1, len(cols)):
        if cols[i] - cols[i - 1] > zone.ctc_x * 1.5:
            groups.append([cols[i]])
        else:
            groups[-1].append(cols[i])

    aisles: dict[str, dict] = {}
    aisle_idx = 1
    yaw_north = round(math.pi / 2, 4)
    yaw_south = round(-math.pi / 2, 4)

    def _add_two_lane_aisle(center_x: float):
        nonlocal aisle_idx
        wps = _make_ns_waypoints(
            center_x - lane_offset, yaw_north, y_min, y_max, spacing)
        if wps:
            aisles[f'aisle_{aisle_idx}'] = wps
            aisle_idx += 1
        wps = _make_ns_waypoints(
            center_x + lane_offset, yaw_south, y_min, y_max, spacing)
        if wps:
            aisles[f'aisle_{aisle_idx}'] = wps
            aisle_idx += 1

    def _add_single_lane(x: float, yaw: float):
        nonlocal aisle_idx
        wps = _make_ns_waypoints(x, yaw, y_min, y_max, spacing)
        if wps:
            aisles[f'aisle_{aisle_idx}'] = wps
            aisle_idx += 1

    # Distance from shelf face to lane in inner aisles
    inner_gap = zone.ctc_x - BIG_SHELF_MESH_WIDTH
    face_clearance = inner_gap / 2.0 - lane_offset

    for group in groups:
        # Left outer: single lane facing the shelf (face east toward column)
        _add_single_lane(
            group[0] - col_half - face_clearance, yaw_south)

        # Inter-column aisles: two lanes
        for i in range(len(group) - 1):
            center = (group[i] + group[i + 1]) / 2.0
            _add_two_lane_aisle(center)

        # Right outer: single lane facing the shelf (face west toward column)
        _add_single_lane(
            group[-1] + col_half + face_clearance, yaw_north)

    return aisles


def generate_waypoints_unpaired_ew(zone: ShelfZone) -> dict:
    """Generate aisle waypoints for E-W unpaired shelf zones.

    Each row gets two lanes (south and north side) with opposite-facing
    yaw to create directional lanes parallel to the shelves.
    """
    rows = zone.row_y_positions
    x_min, x_max = _ew_row_extents(zone)
    offset = SMALL_SHELF_AISLE_OFFSET
    spacing = SMALL_SHELF_WP_SPACING

    aisles: dict[str, dict] = {}
    aisle_idx = 1

    for row_y in rows:
        # South side of this row: face east (yaw = 0)
        aisle_y = row_y - offset
        wps = _make_ew_waypoints(aisle_y, 0.0, x_min, x_max, spacing)
        if wps:
            aisles[f'aisle_{aisle_idx}'] = wps
            aisle_idx += 1

        # North side of this row: face west (yaw = π)
        aisle_y = row_y + offset
        wps = _make_ew_waypoints(
            aisle_y, round(math.pi, 4), x_min, x_max, spacing)
        if wps:
            aisles[f'aisle_{aisle_idx}'] = wps
            aisle_idx += 1

    return aisles


def _compute_zone_d_pair_positions() -> list[tuple[float, float]]:
    """Replicate Zone D pair X positions from generate_warehouse.py logic."""
    d = ZONE_D
    pair_gap = d['pair_gap']
    aisle = d['aisle']
    depth = d['shelf_depth_x']
    step = 2 * pair_gap + aisle

    cross_aisle_breaks = [(-34, -22), (-12, 8), (22, 34)]
    cross_aisle_breaks = [
        (lo + ASSET_X_OFFSET, hi + ASSET_X_OFFSET) for lo, hi in cross_aisle_breaks
    ]

    pairs = []
    x = d['x_min'] + ASSET_X_OFFSET
    while x <= d['x_max'] + ASSET_X_OFFSET + 0.01:
        x2 = x + pair_gap
        half = depth / 2.0
        mid = (x + x2) / 2.0

        s1_ok = (x + half) < CORRIDOR_X_MIN or (x - half) > CORRIDOR_X_MAX
        s2_ok = (x2 + half) < CORRIDOR_X_MIN or (x2 - half) > CORRIDOR_X_MAX
        in_break = any(lo <= mid <= hi for lo, hi in cross_aisle_breaks)

        if s1_ok and s2_ok and not in_break:
            pairs.append((round(x, 2), round(x2, 2)))
        x += step
    return pairs


def generate_waypoints_zone_d() -> dict:
    """Generate aisle waypoints for Zone D.

    Zone D shelves have model yaw=π/2, which rotates the link offset
    (-0.5,0,0) to (0,-0.5,0) in world frame.  Combined with the visual
    yaw=π/2 (total π), the mesh (18.06m × 2.14m) stays as wide E-W
    bands: 18.06m in X and 2.14m in Y, centred at (model_x, model_y-0.5).

    Waypoints are offset from the actual shelf FACE (not the model
    position) to avoid placing them inside the shelf geometry.
    """
    d = ZONE_D
    y_positions = d['y_positions']
    spacing = BIG_SHELF_WP_SPACING
    clearance = 1.93  # metres from shelf face (matches Zone A inner aisles)

    # Zone D link offset rotates to Y: actual shelf center = model_y - 0.5
    link_y_offset = -0.5
    shelf_half_y = BIG_SHELF_MESH_WIDTH / 2.0  # 1.07m

    # X extent: pair positions ± half the actual mesh width in X
    pair_positions = _compute_zone_d_pair_positions()
    if not pair_positions:
        return {}
    mesh_half_x = BIG_SHELF_MESH_LENGTH / 2.0  # 9.03m
    x_min = min(x1 for x1, _ in pair_positions) - mesh_half_x
    x_max = max(x2 for _, x2 in pair_positions) + mesh_half_x

    aisles: dict[str, dict] = {}
    aisle_idx = 1

    for row_y in y_positions:
        actual_y = row_y + link_y_offset
        south_face = actual_y - shelf_half_y
        north_face = actual_y + shelf_half_y

        # South side: offset from south face, face east (yaw = 0)
        aisle_y = south_face - clearance
        wps = _make_ew_waypoints(aisle_y, 0.0, x_min, x_max, spacing)
        if wps:
            aisles[f'aisle_{aisle_idx}'] = wps
            aisle_idx += 1

        # North side: offset from north face, face west (yaw = π)
        aisle_y = north_face + clearance
        wps = _make_ew_waypoints(
            aisle_y, round(math.pi, 4), x_min, x_max, spacing)
        if wps:
            aisles[f'aisle_{aisle_idx}'] = wps
            aisle_idx += 1

    return aisles


def _cluster_bounds(cx: float, cy: float, nx: int, ny: int, sp: float):
    """Return (x_min, x_max, y_min, y_max) for a pallet grid cluster."""
    half_x = (nx - 1) / 2.0 * sp
    half_y = (ny - 1) / 2.0 * sp
    return (cx - half_x, cx + half_x, cy - half_y, cy + half_y)


def generate_waypoints_zone_pickups() -> dict:
    """Generate pickup waypoints around pallet block stacks and inbound staging.

    Places 2-3 waypoints around each cluster at PICKUP_CLEARANCE from the
    cluster edge, facing away from the pallets.  Uses surrounding geometry
    to choose accessible sides.
    """
    cl = PICKUP_CLEARANCE
    yaw_n = round(math.pi / 2, 4)
    yaw_s = round(-math.pi / 2, 4)
    yaw_e = 0.0
    yaw_w = round(math.pi, 4)

    stacks: dict[str, dict] = {}
    stack_idx = 1

    # ── Interior block stacks (2×2 grid) ──
    # Layout:  ps_a(39,33)  ps_c(50,33)
    #          ps_b(39,42)  ps_d(50,42)
    # Gap between a/b and c/d columns (X): ~5.8m — room for points
    # Gap between a/c and b/d rows (Y): ~1.2m — too tight
    for prefix, cx, cy, nx, ny, sp in PALLET_STACKS:
        cx_world = cx + ASSET_X_OFFSET
        x_lo, x_hi, y_lo, y_hi = _cluster_bounds(cx_world, cy, nx, ny, sp)
        mid_x = (x_lo + x_hi) / 2.0
        mid_y = (y_lo + y_hi) / 2.0
        pts: dict[str, dict] = {}
        pt_idx = 1

        if prefix in ('ps_a', 'ps_b', 'ps_c', 'ps_d'):
            is_left_col = prefix in ('ps_a', 'ps_b')
            is_bottom_row = prefix in ('ps_a', 'ps_c')

            # Outer side (away from the other column)
            if is_left_col:
                pts[f'pickup_pt_{pt_idx}'] = {
                    'x': round(x_lo - cl, 2), 'y': round(mid_y, 2),
                    'yaw': yaw_w}
            else:
                pts[f'pickup_pt_{pt_idx}'] = {
                    'x': round(x_hi + cl, 2), 'y': round(mid_y, 2),
                    'yaw': yaw_e}
            pt_idx += 1

            # Open N or S side (away from the other row)
            if is_bottom_row:
                pts[f'pickup_pt_{pt_idx}'] = {
                    'x': round(mid_x, 2), 'y': round(y_lo - cl, 2),
                    'yaw': yaw_s}
            else:
                pts[f'pickup_pt_{pt_idx}'] = {
                    'x': round(mid_x, 2), 'y': round(y_hi + cl, 2),
                    'yaw': yaw_n}
            pt_idx += 1

            # Between-column gap side (faces the other column)
            gap_x = (x_hi + cl) if is_left_col else (x_lo - cl)
            gap_yaw = yaw_e if is_left_col else yaw_w
            pts[f'pickup_pt_{pt_idx}'] = {
                'x': round(gap_x, 2), 'y': round(mid_y, 2),
                'yaw': gap_yaw}

        elif prefix == 'ps_dock':
            # Loading dock — large cluster, points on W and N sides
            pts['pickup_pt_1'] = {
                'x': round(x_lo - cl, 2), 'y': round(mid_y, 2),
                'yaw': yaw_w}
            pts['pickup_pt_2'] = {
                'x': round(mid_x, 2), 'y': round(y_hi + cl, 2),
                'yaw': yaw_n}

        stacks[f'blockstack_{stack_idx}'] = pts
        stack_idx += 1

    # ── Inbound staging clusters ──
    cfg = INBOUND_STAGING
    cols = cfg['cols_per_cluster']
    rows = cfg['rows_per_cluster']
    col_sp = cfg['col_spacing']
    row_sp = cfg['row_spacing']
    y_start = cfg['y_start']

    for cx in cfg['cluster_centers_x']:
        cx_world = cx + ASSET_X_OFFSET
        half_x = (cols - 1) / 2.0 * col_sp
        x_lo = cx_world - half_x
        x_hi = cx_world + half_x
        y_hi = y_start
        y_lo = y_start - (rows - 1) * row_sp
        mid_y = (y_lo + y_hi) / 2.0

        pts = {
            'pickup_pt_1': {
                'x': round(x_lo - cl, 2), 'y': round(mid_y, 2),
                'yaw': yaw_w},
            'pickup_pt_2': {
                'x': round(x_hi + cl, 2), 'y': round(mid_y, 2),
                'yaw': yaw_e},
            'pickup_pt_3': {
                'x': round(cx_world, 2), 'y': round(y_hi + cl, 2),
                'yaw': yaw_n},
        }
        stacks[f'blockstack_{stack_idx}'] = pts
        stack_idx += 1

    return stacks


# ── Main ─────────────────────────────────────────────────────────────

def main():
    default_output = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'config', 'warehouse_waypoints.yaml',
    )

    parser = argparse.ArgumentParser(description='Generate warehouse aisle waypoints.')
    parser.add_argument(
        '-o', '--output', default=default_output,
        help='Output YAML file path (default: ../config/warehouse_waypoints.yaml)',
    )
    args = parser.parse_args()

    waypoints = {
        'zone_a': generate_waypoints_paired_ew(ZONE_A),
        'zone_bw': generate_waypoints_paired_ew(ZONE_B_WEST),
        'zone_be': generate_waypoints_unpaired_ew(ZONE_B_EAST),
        'zone_c': generate_waypoints_unpaired_ew(ZONE_C),
        'zone_d': generate_waypoints_zone_d(),
        'zone_pickups': generate_waypoints_zone_pickups(),
    }

    # Summary
    total = 0
    for zone_name, aisles in waypoints.items():
        zone_count = sum(len(slots) for slots in aisles.values())
        total += zone_count
        print(f'  {zone_name}: {len(aisles)} aisles, {zone_count} waypoints', file=sys.stderr)
    print(f'  TOTAL: {total} waypoints', file=sys.stderr)

    # Write YAML
    output_path = os.path.normpath(args.output)

    header = (
        f'# Warehouse aisle waypoints\n'
        f'# Generated by generate_waypoints.py\n'
        f'# Big shelf spacing: {BIG_SHELF_WP_SPACING}m, offset: {BIG_SHELF_AISLE_OFFSET}m\n'
        f'# Small shelf spacing: {SMALL_SHELF_WP_SPACING}m, offset: {SMALL_SHELF_AISLE_OFFSET}m\n'
        f'#\n'
        f'# Structure: zone -> aisle_N -> slot_N: {{x, y, yaw}}\n'
    )

    yaml_str = yaml.dump(waypoints, default_flow_style=None, sort_keys=False)
    with open(output_path, 'w') as f:
        f.write(header)
        f.write(yaml_str)

    print(f'  Written to: {output_path}', file=sys.stderr)


if __name__ == '__main__':
    main()

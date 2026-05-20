#!/usr/bin/env python3
"""
Generate a 2D occupancy grid map from a RUNNING Gazebo simulation.

Queries the gz-sim scene info service to get all model poses and geometry,
loads mesh files with trimesh for accurate bounding boxes, and renders
a Nav2-compatible .pgm + .yaml occupancy grid.

Prerequisites:
    pip install numpy Pillow PyYAML trimesh

Usage:
    # 1. Launch the sim (headless or GUI):
    ros2 launch opennav_benchmark_sim simulation.launch.py headless:=true

    # 2. Generate the map from the running sim:
    python3 generate_map.py --output-dir ../../opennav_benchmark_nav2/map/

    # Or with custom settings:
    python3 generate_map.py --output-dir /path/to/map --resolution 0.05 --slice-height 0.2
"""

from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

import numpy as np
import yaml
from PIL import Image, ImageDraw

try:
    import trimesh
except ImportError:
    print('ERROR: trimesh not installed. Run: pip install trimesh')
    sys.exit(1)


# ── Scene info parser ───────────────────────────────────────────────

@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    # Quaternion
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    qw: float = 1.0

    def to_matrix(self) -> np.ndarray:
        """Convert pose to 4x4 transform matrix."""
        x, y, z = self.x, self.y, self.z
        qx, qy, qz, qw = self.qx, self.qy, self.qz, self.qw

        # Quaternion to rotation matrix
        m = np.eye(4)
        m[0, 0] = 1 - 2 * (qy * qy + qz * qz)
        m[0, 1] = 2 * (qx * qy - qz * qw)
        m[0, 2] = 2 * (qx * qz + qy * qw)
        m[1, 0] = 2 * (qx * qy + qz * qw)
        m[1, 1] = 1 - 2 * (qx * qx + qz * qz)
        m[1, 2] = 2 * (qy * qz - qx * qw)
        m[2, 0] = 2 * (qx * qz - qy * qw)
        m[2, 1] = 2 * (qx * qy + qz * qw)
        m[2, 2] = 1 - 2 * (qx * qx + qy * qy)
        m[0, 3] = x
        m[1, 3] = y
        m[2, 3] = z
        return m


@dataclass
class BoxGeom:
    sx: float = 1.0
    sy: float = 1.0
    sz: float = 1.0


@dataclass
class CylinderGeom:
    radius: float = 0.5
    length: float = 1.0


@dataclass
class SphereGeom:
    radius: float = 0.5


@dataclass
class MeshGeom:
    filename: str = ''
    scale_x: float = 1.0
    scale_y: float = 1.0
    scale_z: float = 1.0


@dataclass
class PlaneGeom:
    sx: float = 1.0
    sy: float = 1.0


@dataclass
class Visual:
    name: str = ''
    pose: Pose = field(default_factory=Pose)
    geometry: object = None  # BoxGeom, CylinderGeom, MeshGeom, etc.


@dataclass
class Link:
    name: str = ''
    pose: Pose = field(default_factory=Pose)
    visuals: list = field(default_factory=list)


@dataclass
class Model:
    name: str = ''
    pose: Pose = field(default_factory=Pose)
    links: list = field(default_factory=list)


def _parse_float(text: str) -> float:
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


def _parse_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Extract a { ... } block starting at 'start' (the line with '{')."""
    depth = 0
    block_lines = []
    i = start
    while i < len(lines):
        line = lines[i].strip()
        depth += line.count('{') - line.count('}')
        block_lines.append(line)
        if depth <= 0:
            return block_lines, i + 1
        i += 1
    return block_lines, i


def _extract_blocks(block_lines: list[str], tag: str) -> list[list[str]]:
    """Find all sub-blocks with the given tag name."""
    results = []
    i = 0
    while i < len(block_lines):
        line = block_lines[i].strip()
        if line.startswith(f'{tag} {{') or line == f'{tag} {{':
            sub, end = _parse_block(block_lines, i)
            results.append(sub)
            i = end
        elif line.endswith('{') and line.replace('{', '').strip() == tag:
            sub, end = _parse_block(block_lines, i)
            results.append(sub)
            i = end
        else:
            i += 1
    return results


def _get_value(block_lines: list[str], key: str) -> str | None:
    """Get a scalar value like 'key: value' from block lines."""
    for line in block_lines:
        line = line.strip()
        if line.startswith(f'{key}:'):
            return line.split(':', 1)[1].strip().strip('"')
    return None


def _parse_pose_block(block_lines: list[str]) -> Pose:
    """Parse a pose { position { ... } orientation { ... } } block."""
    pose = Pose()
    for pos_block in _extract_blocks(block_lines, 'position'):
        v = _get_value(pos_block, 'x')
        if v:
            pose.x = _parse_float(v)
        v = _get_value(pos_block, 'y')
        if v:
            pose.y = _parse_float(v)
        v = _get_value(pos_block, 'z')
        if v:
            pose.z = _parse_float(v)
    for ori_block in _extract_blocks(block_lines, 'orientation'):
        v = _get_value(ori_block, 'x')
        if v:
            pose.qx = _parse_float(v)
        v = _get_value(ori_block, 'y')
        if v:
            pose.qy = _parse_float(v)
        v = _get_value(ori_block, 'z')
        if v:
            pose.qz = _parse_float(v)
        v = _get_value(ori_block, 'w')
        if v:
            pose.qw = _parse_float(v)
    return pose


def _parse_geometry_block(block_lines: list[str]) -> object:
    """Parse a geometry { ... } block."""
    gtype = _get_value(block_lines, 'type')

    for box_block in _extract_blocks(block_lines, 'box'):
        for size_block in _extract_blocks(box_block, 'size'):
            sx = _parse_float(_get_value(size_block, 'x') or '1')
            sy = _parse_float(_get_value(size_block, 'y') or '1')
            sz = _parse_float(_get_value(size_block, 'z') or '1')
            return BoxGeom(sx, sy, sz)

    for cyl_block in _extract_blocks(block_lines, 'cylinder'):
        r = _parse_float(_get_value(cyl_block, 'radius') or '0.5')
        l = _parse_float(_get_value(cyl_block, 'length') or '1')
        return CylinderGeom(r, l)

    for sph_block in _extract_blocks(block_lines, 'sphere'):
        r = _parse_float(_get_value(sph_block, 'radius') or '0.5')
        return SphereGeom(r)

    for mesh_block in _extract_blocks(block_lines, 'mesh'):
        filename = _get_value(mesh_block, 'filename') or ''
        sx, sy, sz = 1.0, 1.0, 1.0
        for scale_block in _extract_blocks(mesh_block, 'scale'):
            sx = _parse_float(_get_value(scale_block, 'x') or '1')
            sy = _parse_float(_get_value(scale_block, 'y') or '1')
            sz = _parse_float(_get_value(scale_block, 'z') or '1')
        return MeshGeom(filename, sx, sy, sz)

    for plane_block in _extract_blocks(block_lines, 'plane'):
        for size_block in _extract_blocks(plane_block, 'size'):
            sx = _parse_float(_get_value(size_block, 'x') or '1')
            sy = _parse_float(_get_value(size_block, 'y') or '1')
            return PlaneGeom(sx, sy)

    return None


def parse_scene_info(text: str) -> list[Model]:
    """Parse gz scene info protobuf text into Model list."""
    lines = text.splitlines()
    models = []

    model_blocks = _extract_blocks(lines, 'model')
    for mb in model_blocks:
        model = Model()
        model.name = _get_value(mb, 'name') or ''

        for pose_block in _extract_blocks(mb, 'pose'):
            # Only take the first (top-level) pose
            model.pose = _parse_pose_block(pose_block)
            break

        for link_block in _extract_blocks(mb, 'link'):
            link = Link()
            link.name = _get_value(link_block, 'name') or ''
            for lp in _extract_blocks(link_block, 'pose'):
                link.pose = _parse_pose_block(lp)
                break

            for vis_block in _extract_blocks(link_block, 'visual'):
                vis = Visual()
                vis.name = _get_value(vis_block, 'name') or ''
                for vp in _extract_blocks(vis_block, 'pose'):
                    vis.pose = _parse_pose_block(vp)
                    break
                for geom_block in _extract_blocks(vis_block, 'geometry'):
                    vis.geometry = _parse_geometry_block(geom_block)
                    break
                if vis.geometry is not None:
                    link.visuals.append(vis)
            model.links.append(link)
        models.append(model)

    return models


# ── Mesh bounding box cache ──────────────────────────────────────────

_mesh_bounds_cache: dict[str, np.ndarray | None] = {}


def get_mesh_bounds(filename: str) -> np.ndarray | None:
    """Load mesh with trimesh and return bounds array [[min],[max]]."""
    if filename in _mesh_bounds_cache:
        return _mesh_bounds_cache[filename]

    if not os.path.isfile(filename):
        _mesh_bounds_cache[filename] = None
        return None

    try:
        mesh = trimesh.load(filename, force='mesh')
        if hasattr(mesh, 'bounds') and mesh.bounds is not None:
            _mesh_bounds_cache[filename] = mesh.bounds
            return mesh.bounds
        # Scene with multiple geometries
        if hasattr(mesh, 'geometry'):
            all_verts = []
            for geom in mesh.geometry.values():
                all_verts.append(geom.vertices)
            if all_verts:
                verts = np.vstack(all_verts)
                bounds = np.array([verts.min(axis=0), verts.max(axis=0)])
                _mesh_bounds_cache[filename] = bounds
                return bounds
    except Exception as e:
        print(f'  Warning: could not load mesh {filename}: {e}')

    _mesh_bounds_cache[filename] = None
    return None


# ── World-frame shape extraction ─────────────────────────────────────

@dataclass
class WorldShape:
    """A shape in world coordinates ready for 2D projection."""
    model_name: str
    shape_type: str  # 'box', 'cylinder', 'sphere', 'plane'
    # World-frame position and yaw
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0
    # Size (meaning depends on shape_type)
    sx: float = 0.0
    sy: float = 0.0
    sz: float = 0.0


def _matrix_to_yaw(m: np.ndarray) -> float:
    return math.atan2(m[1, 0], m[0, 0])


def extract_world_shapes(models: list[Model]) -> list[WorldShape]:
    """Convert parsed models to world-frame shapes."""
    shapes = []

    for model in models:
        model_tf = model.pose.to_matrix()

        for link in model.links:
            link_tf = link.pose.to_matrix()
            model_link_tf = model_tf @ link_tf

            for vis in link.visuals:
                vis_tf = vis.pose.to_matrix()
                world_tf = model_link_tf @ vis_tf

                wx = world_tf[0, 3]
                wy = world_tf[1, 3]
                wz = world_tf[2, 3]
                wyaw = _matrix_to_yaw(world_tf)

                geom = vis.geometry

                if isinstance(geom, BoxGeom):
                    shapes.append(WorldShape(
                        model.name, 'box', wx, wy, wz, wyaw,
                        geom.sx, geom.sy, geom.sz))

                elif isinstance(geom, CylinderGeom):
                    shapes.append(WorldShape(
                        model.name, 'cylinder', wx, wy, wz, wyaw,
                        geom.radius, geom.radius, geom.length))

                elif isinstance(geom, SphereGeom):
                    shapes.append(WorldShape(
                        model.name, 'sphere', wx, wy, wz, wyaw,
                        geom.radius, geom.radius, geom.radius))

                elif isinstance(geom, PlaneGeom):
                    shapes.append(WorldShape(
                        model.name, 'plane', wx, wy, wz, wyaw,
                        geom.sx, geom.sy, 0.01))

                elif isinstance(geom, MeshGeom):
                    bounds = get_mesh_bounds(geom.filename)
                    if bounds is not None:
                        # Apply mesh scale to bounds
                        scaled_min = bounds[0] * [geom.scale_x, geom.scale_y, geom.scale_z]
                        scaled_max = bounds[1] * [geom.scale_x, geom.scale_y, geom.scale_z]
                        extents = scaled_max - scaled_min
                        center_local = (scaled_min + scaled_max) / 2.0

                        # Transform center to world frame
                        c_homog = np.array([center_local[0], center_local[1],
                                           center_local[2], 1.0])
                        c_world = world_tf @ c_homog

                        shapes.append(WorldShape(
                            model.name, 'box',
                            c_world[0], c_world[1], c_world[2], wyaw,
                            extents[0], extents[1], extents[2]))
                    else:
                        # Unknown mesh, use 1x1x1 fallback
                        shapes.append(WorldShape(
                            model.name, 'box', wx, wy, wz, wyaw,
                            1.0, 1.0, 1.0))

    return shapes


# ── Occupancy grid generation ────────────────────────────────────────

def compute_world_bounds(shapes: list[WorldShape], margin: float = 1.0):
    """Compute bounding box of all shapes, accounting for rotation."""
    if not shapes:
        return -5.0, -5.0, 5.0, 5.0
    bounds = []
    for s in shapes:
        cos_y = abs(math.cos(s.yaw))
        sin_y = abs(math.sin(s.yaw))
        hx, hy = s.sx / 2, s.sy / 2
        ex = hx * cos_y + hy * sin_y
        ey = hx * sin_y + hy * cos_y
        bounds.append((s.x - ex, s.y - ey))
        bounds.append((s.x + ex, s.y + ey))
    xs, ys = zip(*bounds)
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def generate_occupancy_grid(shapes: list[WorldShape], resolution: float = 0.05,
                            margin: float = 1.0, slice_height: float = 0.2,
                            super_sampling: int = 4):
    """Generate occupancy grid from world-frame shapes."""
    # Filter by slice height
    filtered = []
    for s in shapes:
        z_min = s.z - s.sz / 2
        z_max = s.z + s.sz / 2
        if z_min <= slice_height <= z_max:
            filtered.append(s)
    shapes = filtered
    print(f'  {len(shapes)} shapes pass height filter at z={slice_height}m')

    minx, miny, maxx, maxy = compute_world_bounds(shapes, margin)
    w_m, h_m = maxx - minx, maxy - miny
    w = max(100, int(math.ceil(w_m / resolution)))
    h = max(100, int(math.ceil(h_m / resolution)))

    sf = super_sampling
    hr_w, hr_h = w * sf, h * sf
    print(f'  Map: {w}x{h} px  (high-res: {hr_w}x{hr_h})')
    print(f'  World: {w_m:.1f}x{h_m:.1f} m,  resolution: {resolution} m/px')

    img = Image.new('L', (hr_w, hr_h), color=255)
    draw = ImageDraw.Draw(img)

    def world_to_px(wx, wy):
        px = int((wx - minx) * sf / resolution)
        py = hr_h - 1 - int((wy - miny) * sf / resolution)
        return max(0, min(hr_w - 1, px)), max(0, min(hr_h - 1, py))

    for s in shapes:
        if s.shape_type in ('box', 'plane'):
            hx, hy = s.sx / 2, s.sy / 2
            cos_y, sin_y = math.cos(s.yaw), math.sin(s.yaw)
            corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
            px_corners = [world_to_px(cx * cos_y - cy * sin_y + s.x,
                                      cx * sin_y + cy * cos_y + s.y)
                          for cx, cy in corners]
            draw.polygon(px_corners, fill=0, outline=0)

        elif s.shape_type in ('cylinder', 'sphere'):
            px, py = world_to_px(s.x, s.y)
            rp = max(2, int(math.ceil(s.sx * sf / resolution)))
            draw.ellipse([px - rp, py - rp, px + rp, py + rp], fill=0, outline=0)

    # Downsample
    final = img.resize((w, h), Image.LANCZOS)

    # Enhance contrast
    arr = np.array(final)
    arr = np.where(arr > 200, 255, arr)
    arr = np.where(arr < 100, 0, arr)
    mask = (arr >= 100) & (arr <= 200)
    arr[mask] = np.where(arr[mask] < 150, 0, 255)

    return Image.fromarray(arr.astype(np.uint8)), (minx, miny, 0.0)


# ── Main ─────────────────────────────────────────────────────────────

def query_scene_info(world_name: str = 'benchmark_warehouse',
                     timeout: int = 30000) -> str:
    """Query gz-sim scene info service."""
    cmd = [
        'gz', 'service',
        '-s', f'/world/{world_name}/scene/info',
        '--reqtype', 'gz.msgs.Empty',
        '--reptype', 'gz.msgs.Scene',
        '--timeout', str(timeout),
        '-r', '',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f'gz service failed (rc={result.returncode}): {result.stderr}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(
        description='Generate Nav2 occupancy grid from running Gazebo sim')
    parser.add_argument('--output-dir', required=True,
                        help='Output directory for .pgm and .yaml')
    parser.add_argument('--name', default='benchmark_warehouse',
                        help='Base name for output files')
    parser.add_argument('--world', default='benchmark_warehouse',
                        help='Gazebo world name')
    parser.add_argument('--resolution', type=float, default=0.05,
                        help='Map resolution in m/px (default: 0.05)')
    parser.add_argument('--slice-height', type=float, default=0.2,
                        help='Height in metres for 2D slice (default: 0.2)')
    parser.add_argument('--margin', type=float, default=1.0,
                        help='World margin in metres (default: 1.0)')
    parser.add_argument('--super-sampling', type=int, default=4,
                        help='Anti-aliasing factor (default: 4)')
    parser.add_argument('--scene-file', default=None,
                        help='Use pre-captured scene info file instead of querying live sim')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Get scene info
    if args.scene_file:
        print(f'Reading scene from {args.scene_file} ...')
        with open(args.scene_file) as f:
            scene_text = f.read()
    else:
        print(f'Querying live sim (world: {args.world}) ...')
        scene_text = query_scene_info(args.world)

    # Parse scene
    print('Parsing scene info ...')
    models = parse_scene_info(scene_text)
    print(f'  Found {len(models)} models')

    # Extract world-frame shapes
    print('Extracting geometry ...')
    shapes = extract_world_shapes(models)
    print(f'  {len(shapes)} shapes total')

    # Count by type
    type_counts: dict[str, int] = {}
    for s in shapes:
        type_counts[s.shape_type] = type_counts.get(s.shape_type, 0) + 1
    for t, c in sorted(type_counts.items()):
        print(f'    {t}: {c}')

    # Generate map
    print('Generating occupancy grid ...')
    img, origin = generate_occupancy_grid(
        shapes,
        resolution=args.resolution,
        margin=args.margin,
        slice_height=args.slice_height,
        super_sampling=args.super_sampling,
    )

    # Save files
    pgm_path = os.path.join(args.output_dir, f'{args.name}.pgm')
    yaml_path = os.path.join(args.output_dir, f'{args.name}.yaml')

    arr = np.array(img)
    with open(pgm_path, 'wb') as f:
        f.write(b'P5\n')
        f.write(f'{arr.shape[1]} {arr.shape[0]}\n'.encode())
        f.write(b'255\n')
        f.write(arr.tobytes())
    print(f'  Wrote {pgm_path}  ({arr.shape[1]}x{arr.shape[0]})')

    yaml_content = {
        'image': f'{args.name}.pgm',
        'mode': 'trinary',
        'resolution': float(args.resolution),
        'origin': [round(float(origin[0]), 5),
                    round(float(origin[1]), 5),
                    round(float(origin[2]), 5)],
        'negate': 0,
        'occupied_thresh': 0.65,
        'free_thresh': 0.25,
    }
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)
    print(f'  Wrote {yaml_path}')
    print('Done.')


if __name__ == '__main__':
    main()

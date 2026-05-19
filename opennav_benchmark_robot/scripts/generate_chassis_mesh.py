#!/usr/bin/env python3
"""Generate a box chassis with rounded vertical edges (stadium cross-section)."""

import struct
import math
import os


def write_binary_stl(filename, triangles):
    """Write triangles as binary STL. Each triangle is ((v0,v1,v2), normal)."""
    with open(filename, 'wb') as f:
        f.write(b'Generated chassis mesh' + b'\0' * 58)
        f.write(struct.pack('<I', len(triangles)))
        for verts, normal in triangles:
            f.write(struct.pack('<3f', *normal))
            for v in verts:
                f.write(struct.pack('<3f', *v))
            f.write(struct.pack('<H', 0))


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def normalize(v):
    mag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if mag < 1e-10:
        return (0, 0, 1)
    return (v[0]/mag, v[1]/mag, v[2]/mag)


def face_normal(v0, v1, v2):
    return normalize(cross(sub(v1, v0), sub(v2, v0)))


def generate_rounded_box(length, width, height, radius, n_segments=16):
    """
    Box with rounded vertical edges only.
    Top-down cross-section is a stadium/rounded rectangle.
    Vertical faces are flat, top and bottom are flat.
    """
    triangles = []

    half_l = length / 2.0
    half_w = width / 2.0
    half_h = height / 2.0

    # Clamp radius
    r = min(radius, half_l, half_w)

    # Generate the 2D rounded rectangle profile (counter-clockwise)
    # 4 straight segments + 4 quarter-circle corners
    profile = []

    # Corner centers (inset by radius)
    corners = [
        (half_l - r,  half_w - r),   # front-right
        (-half_l + r, half_w - r),    # rear-right... wait
    ]

    # Let's go CCW starting from front-right
    # Corner 0: front-right (+x, +y corner)
    # Corner 1: front-left  (-x, +y corner) -- wait, I need to think in x,y
    # x = length direction, y = width direction
    corner_centers = [
        ( half_l - r,  half_w - r),  # +x, +y
        (-half_l + r,  half_w - r),  # -x, +y
        (-half_l + r, -half_w + r),  # -x, -y
        ( half_l - r, -half_w + r),  # +x, -y
    ]

    # For each corner, generate arc from start_angle
    start_angles = [0, math.pi/2, math.pi, 3*math.pi/2]

    for i in range(4):
        cx, cy = corner_centers[i]
        sa = start_angles[i]
        for j in range(n_segments + 1):
            angle = sa + (math.pi / 2) * j / n_segments
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            profile.append((px, py))

    n_pts = len(profile)

    # Top face (z = +half_h), normal (0,0,1)
    # Fan triangulation from center
    top_center = (0, 0, half_h)
    for i in range(n_pts):
        j = (i + 1) % n_pts
        v0 = top_center
        v1 = (profile[i][0], profile[i][1], half_h)
        v2 = (profile[j][0], profile[j][1], half_h)
        triangles.append(((v0, v1, v2), (0, 0, 1)))

    # Bottom face (z = -half_h), normal (0,0,-1)
    bot_center = (0, 0, -half_h)
    for i in range(n_pts):
        j = (i + 1) % n_pts
        v0 = bot_center
        v1 = (profile[j][0], profile[j][1], -half_h)
        v2 = (profile[i][0], profile[i][1], -half_h)
        triangles.append(((v0, v1, v2), (0, 0, -1)))

    # Side walls (vertical quads between top and bottom profiles)
    for i in range(n_pts):
        j = (i + 1) % n_pts
        tl = (profile[i][0], profile[i][1], half_h)
        tr = (profile[j][0], profile[j][1], half_h)
        bl = (profile[i][0], profile[i][1], -half_h)
        br = (profile[j][0], profile[j][1], -half_h)
        n = face_normal(bl, br, tr)
        triangles.append(((bl, br, tr), n))
        triangles.append(((bl, tr, tl), n))

    return triangles


def generate_sensor_tower(tower_l, tower_w, tower_h, arm_span, arm_thickness, arm_h, radius=0.02, n_seg=8):
    """
    T-shaped sensor tower: vertical column + horizontal crossbar at top.
    arm_span is total tip-to-tip width of the crossbar.
    """
    triangles = []

    # Main column
    triangles.extend(generate_rounded_box(tower_l, tower_w, tower_h, radius, n_seg))

    # Crossbar at top - offset upward
    crossbar = generate_rounded_box(arm_thickness, arm_span, arm_h, radius, n_seg)
    # Shift crossbar up so its bottom aligns with top of column minus arm_h
    z_offset = tower_h / 2.0 - arm_h / 2.0
    shifted = []
    for verts, normal in crossbar:
        new_verts = tuple((v[0], v[1], v[2] + z_offset) for v in verts)
        shifted.append((new_verts, normal))
    triangles.extend(shifted)

    return triangles


def generate_arc_panel(thickness, width, straight_height, arc_radius, edge_radius, n_seg=12, n_arc_seg=32):
    """
    Panel spanning full robot width with a circular arc top.
    - thickness: x-dimension (0.16m)
    - width: y-dimension (0.8m)
    - straight_height: height of straight-walled section below the arc
    - arc_radius: radius of the circular arc on top (determines curvature)
    - edge_radius: rounding on vertical edges (same as chassis, 0.06m)
    - Mesh is centered at its geometric middle (approximately).

    The top surface follows a circular arc: z_top(y) = z_base + sqrt(R^2 - y^2) - sqrt(R^2 - (w/2)^2)
    so that the arc is zero at the edges and peaks at center.
    """
    triangles = []

    half_t = thickness / 2.0
    half_w = width / 2.0

    # Arc geometry: arc_top(y) relative to top of straight section
    # z_arc(y) = sqrt(R^2 - y^2) - sqrt(R^2 - half_w^2)
    # This makes z_arc(±half_w) = 0 and z_arc(0) = R - sqrt(R^2 - half_w^2)
    R = arc_radius
    arc_base_offset = math.sqrt(R * R - half_w * half_w)
    arc_peak = R - arc_base_offset  # height of arc above straight section at center

    # Total height at center
    total_h_center = straight_height + arc_peak
    # Center the mesh vertically: bottom at -total_h_center/2, top at +total_h_center/2 at center
    # Actually, let's center at mid-height of the straight section for simplicity
    z_bottom = -straight_height / 2.0
    z_straight_top = straight_height / 2.0

    def arc_top_z(y):
        """Z coordinate of the arc top at position y."""
        return z_straight_top + math.sqrt(R * R - y * y) - arc_base_offset

    # Generate the 2D rounded rectangle profile in x-y (the cross-section)
    r = min(edge_radius, half_t, half_w)
    corner_centers = [
        ( half_t - r,  half_w - r),  # +x, +y
        (-half_t + r,  half_w - r),  # -x, +y
        (-half_t + r, -half_w + r),  # -x, -y
        ( half_t - r, -half_w + r),  # +x, -y
    ]
    start_angles = [0, math.pi/2, math.pi, 3*math.pi/2]

    profile = []
    for i in range(4):
        cx, cy = corner_centers[i]
        sa = start_angles[i]
        for j in range(n_seg + 1):
            angle = sa + (math.pi / 2) * j / n_seg
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            profile.append((px, py))

    n_pts = len(profile)

    # For the arc top, we need to generate the top surface as a curved sheet
    # The y-coordinates of the profile vary, so the top z varies per profile point
    # Generate top face: fan from center using arc_top_z for each point's y
    top_center_z = arc_top_z(0)
    top_center = (0, 0, top_center_z)
    for i in range(n_pts):
        j = (i + 1) % n_pts
        y_i = profile[i][1]
        y_j = profile[j][1]
        # Clamp y to valid arc range
        y_i_clamped = max(-half_w + 0.001, min(half_w - 0.001, y_i))
        y_j_clamped = max(-half_w + 0.001, min(half_w - 0.001, y_j))
        z_i = arc_top_z(y_i_clamped)
        z_j = arc_top_z(y_j_clamped)
        v0 = top_center
        v1 = (profile[i][0], profile[i][1], z_i)
        v2 = (profile[j][0], profile[j][1], z_j)
        n = face_normal(v0, v1, v2)
        triangles.append(((v0, v1, v2), n))

    # Bottom face (flat)
    bot_center = (0, 0, z_bottom)
    for i in range(n_pts):
        j = (i + 1) % n_pts
        v0 = bot_center
        v1 = (profile[j][0], profile[j][1], z_bottom)
        v2 = (profile[i][0], profile[i][1], z_bottom)
        triangles.append(((v0, v1, v2), (0, 0, -1)))

    # Side walls: from bottom to arc top, segmented vertically for the arc
    # We need vertical strips on the side walls that follow the arc
    n_z_seg = 8  # vertical segments for the curved portion
    for i in range(n_pts):
        j = (i + 1) % n_pts
        y_i = profile[i][1]
        y_j = profile[j][1]
        y_i_clamped = max(-half_w + 0.001, min(half_w - 0.001, y_i))
        y_j_clamped = max(-half_w + 0.001, min(half_w - 0.001, y_j))
        z_top_i = arc_top_z(y_i_clamped)
        z_top_j = arc_top_z(y_j_clamped)

        # Single quad from bottom to top (since vertical edges are straight)
        bl = (profile[i][0], profile[i][1], z_bottom)
        br = (profile[j][0], profile[j][1], z_bottom)
        tl = (profile[i][0], profile[i][1], z_top_i)
        tr = (profile[j][0], profile[j][1], z_top_j)
        n = face_normal(bl, br, tr)
        triangles.append(((bl, br, tr), n))
        triangles.append(((bl, tr, tl), n))

    return triangles


if __name__ == '__main__':
    mesh_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'meshes')
    os.makedirs(mesh_dir, exist_ok=True)

    # Chassis: 1.2m x 0.8m x 0.3m, 0.06m radius on vertical edges
    print("Generating chassis mesh...")
    tris = generate_rounded_box(1.2, 0.8, 0.3, radius=0.06, n_segments=12)
    path = os.path.join(mesh_dir, 'chassis_body.stl')
    write_binary_stl(path, tris)
    print(f"  Wrote {path} ({len(tris)} triangles)")

    # Sensor tower: arc panel, 0.16m thick x 0.8m wide, circular arc top
    # Arc radius 0.927m gives 15deg tangent at y=±0.24m (matching lidar tilts)
    # Straight section: 0.22m, arc adds ~0.09m at center
    print("Generating sensor tower (arc panel) mesh...")
    tris = generate_arc_panel(
        thickness=0.16, width=0.8, straight_height=0.22,
        arc_radius=0.927, edge_radius=0.06, n_seg=12, n_arc_seg=32)
    path = os.path.join(mesh_dir, 'sensor_tower.stl')
    write_binary_stl(path, tris)
    print(f"  Wrote {path} ({len(tris)} triangles)")

    print("Done!")

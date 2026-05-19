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


def generate_arc_panel(thickness, width, wall_height, arc_radius, edge_radius, n_seg=12, n_arc_pts=48):
    """
    Solid panel with arc top, extruded flat along x.

    Front (+x) face follows chassis rounding at y-edges (edge_radius).
    Back (-x) face is flat at -half_t for full width.
    All surfaces (top, front, back, bottom) are generated from the same
    y-sample points so they share edges — no T-junctions or gaps.

    - thickness: x-dimension (0.16m)
    - width: y-dimension (0.8m)
    - wall_height: height at the edges (y=±half_w)
    - arc_radius: R of the circular arc on top (y-z curve)
    - edge_radius: rounding on front y-corners (matching chassis)

    Mesh is centered at z=0 (half of total center height).
    """
    triangles = []

    half_t = thickness / 2.0
    half_w = width / 2.0
    R = arc_radius
    r = min(edge_radius, half_t, half_w)

    # Arc geometry
    arc_peak = R - math.sqrt(R * R - half_w * half_w)
    total_h_center = wall_height + arc_peak
    half_h = total_h_center / 2.0
    z_bottom = -half_h

    def z_top(y):
        """Top surface z at position y (arc profile)."""
        y_c = max(-half_w + 0.0001, min(half_w - 0.0001, y))
        drop = R - math.sqrt(R * R - y_c * y_c)
        return half_h - drop

    def front_x(y):
        """Front (+x) edge at position y, with chassis-matching rounding."""
        abs_y = abs(y)
        if abs_y <= half_w - r:
            return half_t
        else:
            dy = abs_y - (half_w - r)
            if dy >= r:
                return half_t - r
            return half_t - r + math.sqrt(max(0, r * r - dy * dy))

    back_x = -half_t  # back face is completely flat

    # Generate y sample points — dense everywhere, extra in corners
    y_set = set()
    for i in range(n_arc_pts + 1):
        y_set.add(-half_w + (i / n_arc_pts) * width)
    # Extra samples in corner regions for smooth rounding
    for sign in [-1, 1]:
        corner_start = sign * (half_w - r)
        for j in range(n_seg + 1):
            y_set.add(corner_start + sign * r * j / n_seg)
    y_sorted = sorted(y_set)

    # All surfaces use the same y_sorted so they share edge vertices.

    # --- TOP SURFACE (arc in y, flat across x) ---
    for i in range(len(y_sorted) - 1):
        y0, y1 = y_sorted[i], y_sorted[i + 1]
        z0, z1 = z_top(y0), z_top(y1)
        fx0, fx1 = front_x(y0), front_x(y1)
        fl = (fx0, y0, z0)
        fr = (fx1, y1, z1)
        br = (back_x, y1, z1)
        bl = (back_x, y0, z0)
        n1 = face_normal(fl, fr, br)
        n2 = face_normal(fl, br, bl)
        triangles.append(((fl, fr, br), n1))
        triangles.append(((fl, br, bl), n2))

    # --- BOTTOM FACE (flat) ---
    for i in range(len(y_sorted) - 1):
        y0, y1 = y_sorted[i], y_sorted[i + 1]
        fx0, fx1 = front_x(y0), front_x(y1)
        fl = (fx0, y0, z_bottom)
        fr = (fx1, y1, z_bottom)
        br = (back_x, y1, z_bottom)
        bl = (back_x, y0, z_bottom)
        triangles.append(((fl, br, fr), (0, 0, -1)))
        triangles.append(((fl, bl, br), (0, 0, -1)))

    # --- FRONT WALL (follows rounding, from z_bottom to z_top) ---
    for i in range(len(y_sorted) - 1):
        y0, y1 = y_sorted[i], y_sorted[i + 1]
        fx0, fx1 = front_x(y0), front_x(y1)
        z0t, z1t = z_top(y0), z_top(y1)
        bl = (fx0, y0, z_bottom)
        br = (fx1, y1, z_bottom)
        tr = (fx1, y1, z1t)
        tl = (fx0, y0, z0t)
        n1 = face_normal(bl, br, tr)
        n2 = face_normal(bl, tr, tl)
        triangles.append(((bl, br, tr), n1))
        triangles.append(((bl, tr, tl), n2))

    # --- BACK WALL (flat at x = -half_t, from z_bottom to z_top) ---
    for i in range(len(y_sorted) - 1):
        y0, y1 = y_sorted[i], y_sorted[i + 1]
        z0t, z1t = z_top(y0), z_top(y1)
        bl = (back_x, y0, z_bottom)
        br = (back_x, y1, z_bottom)
        tr = (back_x, y1, z1t)
        tl = (back_x, y0, z0t)
        n1 = face_normal(bl, tl, tr)
        n2 = face_normal(bl, tr, br)
        triangles.append(((bl, tl, tr), n1))
        triangles.append(((bl, tr, br), n2))

    # --- LEFT SIDE WALL (y = -half_w, normal faces -y) ---
    fx = front_x(-half_w)
    zt = z_top(-half_w)
    bl = (back_x, -half_w, z_bottom)
    br = (fx, -half_w, z_bottom)
    tr = (fx, -half_w, zt)
    tl = (back_x, -half_w, zt)
    triangles.append(((bl, br, tr), (0, -1, 0)))
    triangles.append(((bl, tr, tl), (0, -1, 0)))

    # --- RIGHT SIDE WALL (y = +half_w, normal faces +y) ---
    fx = front_x(half_w)
    zt = z_top(half_w)
    bl = (fx, half_w, z_bottom)
    br = (back_x, half_w, z_bottom)
    tr = (back_x, half_w, zt)
    tl = (fx, half_w, zt)
    triangles.append(((bl, br, tr), (0, 1, 0)))
    triangles.append(((bl, tr, tl), (0, 1, 0)))

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

    # Sensor tower: arc panel, 0.16m thick x 0.8m wide
    # Solid panel with arc top surface (R=1.5m), flat front/back faces
    # wall_height=0.28m at edges, arc adds ~0.055m at center
    # Total height at center: ~0.335m (centered: ±0.167)
    # Arc drop at y=0.24: ~0.019m, at y=0.4 (edge): ~0.055m
    print("Generating sensor tower (arc panel) mesh...")
    tris = generate_arc_panel(
        thickness=0.16, width=0.8, wall_height=0.28,
        arc_radius=1.5, edge_radius=0.06, n_seg=12, n_arc_pts=48)
    path = os.path.join(mesh_dir, 'sensor_tower.stl')
    write_binary_stl(path, tris)
    print(f"  Wrote {path} ({len(tris)} triangles)")

    print("Done!")

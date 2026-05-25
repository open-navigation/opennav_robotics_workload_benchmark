#!/usr/bin/env python3
# Copyright 2025 Open Navigation LLC
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

"""ROS 2 node that publishes warehouse waypoints as a MarkerArray for RViz."""

import math
import os

import yaml

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import ColorRGBA
from visualization_msgs.msg import Marker, MarkerArray

# Zone colours (RGBA)
ZONE_COLORS = {
    'zone_a': ColorRGBA(r=1.0, g=0.2, b=0.2, a=0.9),
    'zone_bw': ColorRGBA(r=0.2, g=0.8, b=0.2, a=0.9),
    'zone_be': ColorRGBA(r=0.2, g=0.4, b=1.0, a=0.9),
    'zone_c': ColorRGBA(r=1.0, g=0.8, b=0.0, a=0.9),
    'zone_d': ColorRGBA(r=0.8, g=0.2, b=1.0, a=0.9),
    'zone_pickups': ColorRGBA(r=1.0, g=0.5, b=0.0, a=0.9),
}

# Shortened zone name prefixes for marker labels
ZONE_ABBREV = {
    'zone_a': 'za',
    'zone_bw': 'zbw',
    'zone_be': 'zbe',
    'zone_c': 'zc',
    'zone_d': 'zd',
    'zone_pickups': 'zp',
}


class WaypointVisualizer(Node):

    def __init__(self):
        super().__init__('waypoint_visualizer')

        self.declare_parameter('waypoints_file', '')

        latched_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.pub = self.create_publisher(MarkerArray, '/waypoint_markers', latched_qos)

        waypoints_file = self.get_parameter('waypoints_file').value
        if not waypoints_file:
            pkg = get_package_share_directory('opennav_benchmark_sim')
            waypoints_file = os.path.join(pkg, 'config', 'warehouse_waypoints.yaml')

        self._load_and_publish(waypoints_file)

    def _load_and_publish(self, filepath):
        with open(filepath) as f:
            data = yaml.safe_load(f)

        marker_array = MarkerArray()
        marker_id = 0

        for zone_name, aisles in data.items():
            color = ZONE_COLORS.get(
                zone_name, ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0)
            )
            zone_abbrev = ZONE_ABBREV.get(zone_name, zone_name)

            for aisle_name, slots in aisles.items():
                aisle_num = aisle_name.replace('aisle_', 'a').replace(
                    'blockstack_', 'bs')

                for slot_name, wp in slots.items():
                    slot_num = slot_name.replace('slot_', 's').replace(
                        'pickup_pt_', 'p')
                    short_id = f'{zone_abbrev}_{aisle_num}_{slot_num}'

                    # Arrow marker: position + yaw
                    m = Marker()
                    m.header.frame_id = 'map'
                    m.ns = f'{zone_name}/{aisle_name}'
                    m.id = marker_id
                    m.type = Marker.ARROW
                    m.action = Marker.ADD
                    m.pose.position.x = float(wp['x'])
                    m.pose.position.y = float(wp['y'])
                    m.pose.position.z = 0.1
                    yaw = float(wp['yaw'])
                    m.pose.orientation.z = math.sin(yaw / 2.0)
                    m.pose.orientation.w = math.cos(yaw / 2.0)
                    m.scale.x = 0.6
                    m.scale.y = 0.15
                    m.scale.z = 0.15
                    m.color = color
                    marker_array.markers.append(m)
                    marker_id += 1

                    # Text label
                    t = Marker()
                    t.header.frame_id = 'map'
                    t.ns = f'{zone_name}/{aisle_name}/labels'
                    t.id = marker_id
                    t.type = Marker.TEXT_VIEW_FACING
                    t.action = Marker.ADD
                    t.pose.position.x = float(wp['x'])
                    t.pose.position.y = float(wp['y'])
                    t.pose.position.z = 0.5
                    t.scale.z = 0.3
                    t.color = color
                    t.text = short_id
                    marker_array.markers.append(t)
                    marker_id += 1

        self.pub.publish(marker_array)
        self.get_logger().info(
            f'Published {marker_id} markers ({marker_id // 2} waypoints) '
            f'from {filepath}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = WaypointVisualizer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3

import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan
import tf2_ros
from tf2_ros import TransformException


class LaserScanMerger(Node):
    def __init__(self):
        super().__init__('laserscan_merger')

        self.declare_parameter('destination_frame', 'base_link')
        self.declare_parameter('scan_topics', ['/scan_front_left', '/scan_front_right'])
        self.declare_parameter('merged_scan_topic', '/scan_merged')
        self.declare_parameter('angle_min', -math.pi)
        self.declare_parameter('angle_max', math.pi)
        self.declare_parameter('angle_increment', 0.006544)
        self.declare_parameter('range_min', 0.1)
        self.declare_parameter('range_max', 25.0)

        self.dest_frame = self.get_parameter('destination_frame').value
        self.scan_topics = self.get_parameter('scan_topics').value
        self.angle_min = self.get_parameter('angle_min').value
        self.angle_max = self.get_parameter('angle_max').value
        self.angle_increment = self.get_parameter('angle_increment').value
        self.range_min = self.get_parameter('range_min').value
        self.range_max = self.get_parameter('range_max').value

        self.num_bins = int((self.angle_max - self.angle_min) / self.angle_increment)
        self.latest_scans = {}

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=5
        )

        for topic in self.scan_topics:
            self.create_subscription(
                LaserScan, topic,
                lambda msg, t=topic: self.scan_callback(msg, t),
                sensor_qos
            )
            self.get_logger().info(f'Subscribed to {topic}')

        merged_topic = self.get_parameter('merged_scan_topic').value
        self.merged_pub = self.create_publisher(LaserScan, merged_topic, sensor_qos)
        self.get_logger().info(
            f'Publishing merged scan on {merged_topic} in frame {self.dest_frame}'
        )

    def scan_callback(self, msg, topic):
        self.latest_scans[topic] = msg
        if len(self.latest_scans) == len(self.scan_topics):
            self.publish_merged_scan()

    def publish_merged_scan(self):
        ranges = np.full(self.num_bins, float('inf'))
        latest_stamp = None

        for topic, scan in self.latest_scans.items():
            stamp = rclpy.time.Time.from_msg(scan.header.stamp)
            if latest_stamp is None or stamp > latest_stamp:
                latest_stamp = stamp
            try:
                transform = self.tf_buffer.lookup_transform(
                    self.dest_frame, scan.header.frame_id,
                    rclpy.time.Time.from_msg(scan.header.stamp),
                    timeout=rclpy.duration.Duration(seconds=0.1)
                )
            except TransformException as e:
                self.get_logger().warn(f'TF lookup failed for {scan.header.frame_id}: {e}')
                continue

            tx = transform.transform.translation.x
            ty = transform.transform.translation.y
            q = transform.transform.rotation
            yaw = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            )

            angles = np.arange(
                scan.angle_min,
                scan.angle_min + len(scan.ranges) * scan.angle_increment,
                scan.angle_increment
            )[:len(scan.ranges)]
            scan_ranges = np.array(scan.ranges)

            valid = np.isfinite(scan_ranges) & (scan_ranges >= scan.range_min) & (scan_ranges <= scan.range_max)
            angles = angles[valid]
            scan_ranges = scan_ranges[valid]

            # Transform points to destination frame
            local_x = scan_ranges * np.cos(angles)
            local_y = scan_ranges * np.sin(angles)
            cos_yaw = math.cos(yaw)
            sin_yaw = math.sin(yaw)
            dest_x = cos_yaw * local_x - sin_yaw * local_y + tx
            dest_y = sin_yaw * local_x + cos_yaw * local_y + ty

            dest_angles = np.arctan2(dest_y, dest_x)
            dest_ranges = np.sqrt(dest_x ** 2 + dest_y ** 2)

            # Bin into merged scan (keep closest range per bin)
            bin_indices = ((dest_angles - self.angle_min) / self.angle_increment).astype(int)
            in_bounds = (bin_indices >= 0) & (bin_indices < self.num_bins)
            bin_indices = bin_indices[in_bounds]
            dest_ranges = dest_ranges[in_bounds]

            # For each bin, keep minimum range
            np.minimum.at(ranges, bin_indices, dest_ranges)

        # Build merged LaserScan message
        merged = LaserScan()
        merged.header.stamp = latest_stamp.to_msg()
        merged.header.frame_id = self.dest_frame
        merged.angle_min = self.angle_min
        merged.angle_max = self.angle_max
        merged.angle_increment = self.angle_increment
        merged.time_increment = 0.0
        merged.scan_time = 0.033333
        merged.range_min = self.range_min
        merged.range_max = self.range_max

        # Replace inf with 0.0 (no return)
        ranges[np.isinf(ranges)] = 0.0
        merged.ranges = ranges.tolist()

        self.merged_pub.publish(merged)


def main(args=None):
    rclpy.init(args=args)
    node = LaserScanMerger()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

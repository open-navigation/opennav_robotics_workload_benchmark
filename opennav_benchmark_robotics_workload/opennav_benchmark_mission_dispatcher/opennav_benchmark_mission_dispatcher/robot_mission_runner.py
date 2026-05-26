#! /usr/bin/env python3
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
A long-duration, indoor picking benchmark that continuously dispatches
pick-and-place missions. Every 1000 missions, the robot docks for a
simulated charge cycle (10s), then resumes. Runs until Ctrl-C.
"""

import math
import os
import time

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node

from nav2_simple_commander.robot_navigator import TaskResult

from .task_dispatcher import TaskDispatcher

MISSIONS_PER_CHARGE = 1000
CHARGE_WAIT_SECONDS = 10
MAX_RETRIES = 3


class RobotMissionRunner(Node):
    """A long-duration, indoor picking benchmark using Nav2 and a task dispatcher."""

    def __init__(self):
        super().__init__('robot_mission_runner')
        self.navigator = BasicNavigator()

        # Load annotations from installed package share
        application_pkg = get_package_share_directory('opennav_benchmark_mission_dispatcher')
        annotations_file = os.path.join(
            application_pkg, 'annotations', 'warehouse_waypoints.yaml')
        self.dispatcher = TaskDispatcher(annotations_file, self)

        self.get_logger().info('Sending initial pose...')
        self.setInitialPose()
        self.get_logger().info('Waiting for Nav2 to become active...')
        self.waitUntilActive()
        self.get_logger().info('Nav2 up, picking benchmark node started!')

    def waitUntilActive(self):
        """Block until the navigation system is up and running."""
        self.navigator._waitForNodeToActivate('bt_navigator')
        self.get_logger().info('Nav2 is ready for use!')

    def setInitialPose(self):
        """Publish the initial pose of the robot at the dock."""
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        pose.pose.position.x = 63.001
        pose.pose.position.y = 36.551
        yaw = -3.139
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        self.navigator.setInitialPose(pose)
        time.sleep(3)  # Wait for initial pose to be processed

    def wpToPose(self, wp):
        """
        Convert a waypoint dict to a PoseStamped.

        :param wp: Waypoint dict with 'x', 'y', 'yaw' keys.
        :return: PoseStamped in the map frame.
        """
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        pose.pose.position.x = float(wp['x'])
        pose.pose.position.y = float(wp['y'])
        yaw = float(wp['yaw'])
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    def navigateToWaypoint(self, wp):
        """
        Navigate to a waypoint and block until complete.

        :param wp: Waypoint dict with 'x', 'y', 'yaw' keys.
        :return: True if navigation succeeded, False otherwise.
        """
        self.navigator.clearAllCostmaps()
        nav_start = self.navigator.get_clock().now()
        last_log_time = self.navigator.get_clock().now()
        self.navigator.goToPose(self.wpToPose(wp))
        while not self.navigator.isTaskComplete() and rclpy.ok():
            now = self.navigator.get_clock().now()
            if now - last_log_time >= Duration(seconds=5.0):
                last_log_time = now
                feedback = self.navigator.getFeedback()
                if feedback:
                    pos = feedback.current_pose.pose.position
                    nav_time = feedback.navigation_time
                    eta = feedback.estimated_time_remaining
                    self.get_logger().info(
                        f'Pose: ({pos.x:.2f}, {pos.y:.2f}), '
                        f'Elapsed: {nav_time.sec}s, '
                        f'ETA: {eta.sec}s, '
                        f'Dist remaining: {feedback.distance_remaining:.2f}m')
            time.sleep(0.1)

        result = self.navigator.getResult()
        self.get_logger().info(f'Navigation result: {result.name}')
        return result == TaskResult.SUCCEEDED

    def navigateWithRetries(self, wp, label):
        """
        Navigate to a waypoint with up to MAX_RETRIES attempts.

        :param wp: Waypoint dict with 'x', 'y', 'yaw' keys.
        :param label: Description of this navigation for logging.
        :return: True if navigation succeeded, False if all retries exhausted.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            self.get_logger().info(f'{label}, attempt {attempt}/{MAX_RETRIES}...')
            if self.navigateToWaypoint(wp):
                return True
            self.get_logger().warn(f'{label} attempt {attempt} failed.')
        return False

    def runMission(self):
        """
        Execute a single pick-and-place mission: pick then drop.

        Each navigation leg is retried independently up to MAX_RETRIES times.

        :return: True if the mission succeeded, False otherwise.
        """
        pick_wp = self.dispatcher.get_next_pick()
        drop_wp = self.dispatcher.get_next_drop()
        self.get_logger().info(f'Picking from {pick_wp}, dropping at {drop_wp}...')

        # Navigate to pick location, simulate picking (10s)
        if not self.navigateWithRetries(pick_wp, 'Navigating to pick'):
            return False
        time.sleep(10)

        # Navigate to drop location, simulate dropping (10s)
        if not self.navigateWithRetries(drop_wp, 'Navigating to drop'):
            return False
        time.sleep(10)
        return True

    def chargeCycle(self):
        """Dock, wait for simulated charge, then undock."""
        self.get_logger().info(f'Docking for charge cycle ({CHARGE_WAIT_SECONDS}s)...')
        self.navigator.dockRobotByID('home_dock', nav_to_dock=True)
        while not self.navigator.isTaskComplete() and rclpy.ok():
            time.sleep(0.1)

        time.sleep(CHARGE_WAIT_SECONDS)

        self.navigator.undockRobot(dock_type='simple_charging_dock')
        while not self.navigator.isTaskComplete() and rclpy.ok():
            time.sleep(0.1)

        self.get_logger().info('Charge cycle complete, resuming missions.')

    def run(self):
        """Run pick-and-place missions continuously."""
        self.navigator.clearAllCostmaps()

        self.navigator.undockRobot(dock_type='simple_charging_dock')
        while not self.navigator.isTaskComplete() and rclpy.ok():
            time.sleep(0.1)
        self.navigator.backup(backup_dist=0.5, backup_speed=0.40)
        while not self.navigator.isTaskComplete() and rclpy.ok():
            time.sleep(0.1)

        mission_count = 0
        while rclpy.ok():
            mission_count += 1
            if not self.runMission():
                self.get_logger().warn(
                    f'Mission {mission_count} failed after retries, '
                    'returning to dock for charge cycle.')
                self.chargeCycle()
                continue

            self.get_logger().info(f'Mission {mission_count} completed.')
            if mission_count % MISSIONS_PER_CHARGE == 0:
                self.chargeCycle()


def main():
    rclpy.init()
    node = RobotMissionRunner()
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

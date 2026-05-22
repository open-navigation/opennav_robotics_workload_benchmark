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
Dispatcher interface to get next pick and drop location tasks.
Picks are from blockstack / loading dock areas (zone_pickups).
Drops are to zoned shelving (zone_a, zone_bw, zone_be, zone_c, zone_d).
"""

import random

import yaml

PICK_ZONES = ['zone_pickups']
DROP_ZONES = ['zone_a', 'zone_bw', 'zone_be', 'zone_c', 'zone_d']


class TaskDispatcher:
    """
    Dispatcher interface to assign pick and drop location tasks.

    Parses a warehouse annotations YAML file and builds databases of
    picking locations (blockstacks, loading docks) and drop locations
    (zoned shelving aisles). Provides a public interface to request
    the next pick or drop task, which would be replaced by a real
    centralized cloud warehouse management system in production.
    """

    def __init__(self, annotations_filepath):
        """
        Parse the warehouse annotations YAML into pick and drop databases.

        :param annotations_filepath: Path to the warehouse annotations YAML file.
        """
        random.seed(42)
        with open(annotations_filepath) as f:
            data = yaml.safe_load(f)

        # Build flat lists of pick and drop waypoints:
        # Each entry is {'x': float, 'y': float, 'yaw': float}
        self.picking_locations = {}
        self.drop_locations = {}

        for zone_name, aisles in data.items():
            if zone_name in PICK_ZONES:
                for aisle_name, slots in aisles.items():
                    for slot_name, wp in slots.items():
                        key = f'{zone_name}/{aisle_name}/{slot_name}'
                        self.picking_locations[key] = wp
            elif zone_name in DROP_ZONES:
                for aisle_name, slots in aisles.items():
                    for slot_name, wp in slots.items():
                        key = f'{zone_name}/{aisle_name}/{slot_name}'
                        self.drop_locations[key] = wp

    def get_next_picks(self, num_picks=1):
        """
        Get a list of pick locations.

        :param num_picks: Number of pick locations to return.
        :return: List of pick waypoints, each ``{'x': float, 'y': float, 'yaw': float}``.
        """
        picks = []
        for _ in range(num_picks):
            picks.append(self.get_next_pick())
        return picks

    def get_next_drops(self, num_drops=1):
        """
        Get a list of drop locations.

        :param num_drops: Number of drop locations to return.
        :return: List of drop waypoints, each ``{'x': float, 'y': float, 'yaw': float}``.
        """
        drops = []
        for _ in range(num_drops):
            drops.append(self.get_next_drop())
        return drops

    def get_next_pick(self):
        """
        Get the next pick location from a blockstack or loading dock area.

        Would be replaced by a request from a centralized system.

        :return: A pick waypoint ``{'x': float, 'y': float, 'yaw': float}``.
        """
        key = random.choice(list(self.picking_locations.keys()))
        return self.picking_locations[key]

    def get_next_drop(self):
        """
        Get the next drop location in the zoned shelving area.

        Would be replaced by a request from a centralized system.

        :return: A drop waypoint ``{'x': float, 'y': float, 'yaw': float}``.
        """
        key = random.choice(list(self.drop_locations.keys()))
        return self.drop_locations[key]

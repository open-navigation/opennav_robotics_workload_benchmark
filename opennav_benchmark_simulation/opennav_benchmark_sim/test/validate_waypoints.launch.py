import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import OpaqueFunction
from launch_ros.actions import LifecycleNode, Node


def launch_setup(context):
    sim_pkg = get_package_share_directory('opennav_benchmark_sim')
    nav2_pkg = get_package_share_directory('opennav_benchmark_nav2')

    map_yaml = os.path.join(nav2_pkg, 'map', 'benchmark_warehouse.yaml')
    waypoints_yaml = os.path.join(sim_pkg, 'config', 'warehouse_waypoints.yaml')
    rviz_config = os.path.join(sim_pkg, 'test', 'validate_waypoints.rviz')

    # Map server (lifecycle node)
    map_server = LifecycleNode(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        namespace='',
        output='screen',
        parameters=[{
            'yaml_filename': map_yaml,
            'use_sim_time': False,
        }],
    )

    # Lifecycle manager to auto-configure and activate map_server
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager',
        output='screen',
        parameters=[{
            'autostart': True,
            'node_names': ['map_server'],
            'use_sim_time': False,
        }],
    )

    # Waypoint visualizer
    visualizer = Node(
        package='opennav_benchmark_sim',
        executable='visualize_waypoints.py',
        name='waypoint_visualizer',
        output='screen',
        parameters=[{
            'waypoints_file': waypoints_yaml,
        }],
    )

    # RViz
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': False}],
        output='screen',
    )

    return [map_server, lifecycle_manager, visualizer, rviz]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup),
    ])

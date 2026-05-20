import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    nav2_pkg = get_package_share_directory('opennav_benchmark_nav2')
    nav2_bringup_pkg = get_package_share_directory('nav2_bringup')

    default_params = os.path.join(nav2_pkg, 'config', 'nav2_params.yaml')

    slam = LaunchConfiguration('slam')
    map_yaml_file = LaunchConfiguration('map')
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')
    autostart = LaunchConfiguration('autostart')

    return LaunchDescription([
        DeclareLaunchArgument(
            'slam', default_value='False',
            description='Whether to run SLAM'),
        DeclareLaunchArgument(
            'map', default_value=os.path.join(nav2_pkg, 'map', 'benchmark_warehouse_map.yaml'),
            description='Full path to map yaml file to load'),
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Use simulation clock'),
        DeclareLaunchArgument(
            'params_file', default_value=default_params,
            description='Nav2 parameters file'),
        DeclareLaunchArgument(
            'autostart', default_value='true',
            description='Automatically startup the nav2 stack'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav2_bringup_pkg, 'launch', 'bringup_launch.py')
            ),
            launch_arguments={
                'slam': slam,
                'map': map_yaml_file,
                'use_sim_time': use_sim_time,
                'params_file': params_file,
                'autostart': autostart,
                'use_composition': 'True',
                'use_respawn': 'False',
            }.items(),
        ),
    ])

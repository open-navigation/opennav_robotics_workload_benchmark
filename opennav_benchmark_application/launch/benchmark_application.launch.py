import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    nav2_pkg = get_package_share_directory('opennav_benchmark_nav2')
    vlm_pkg = get_package_share_directory('opennav_benchmark_vlm')

    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Use the /clock topic for time'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav2_pkg, 'launch', 'navigation.launch.py')
            ),
            launch_arguments={
                'use_sim_time': use_sim_time,
            }.items(),
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(vlm_pkg, 'launch', 'vlm.launch.py')
            ),
        ),

        Node(
            package='opennav_benchmark_application',
            executable='robot_mission_runner',
            name='robot_mission_runner',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time}],
        ),
    ])

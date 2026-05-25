from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    params_file = PathJoinSubstitution([
        FindPackageShare('opennav_benchmark_vlm'),
        'config',
        'vlm_params.yaml',
    ])

    return LaunchDescription([
        Node(
            package='opennav_benchmark_vlm',
            executable='vlm_node',
            name='vlm_node',
            output='screen',
            parameters=[params_file],
        ),
    ])

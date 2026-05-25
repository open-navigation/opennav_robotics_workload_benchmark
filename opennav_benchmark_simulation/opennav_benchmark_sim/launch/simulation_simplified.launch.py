import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    sim_pkg = get_package_share_directory('opennav_benchmark_sim')
    simplified_world = os.path.join(
        sim_pkg, 'worlds', 'benchmark_warehouse_simplified.sdf.xacro')

    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(sim_pkg, 'launch', 'simulation.launch.py')),
            launch_arguments={'world': simplified_world}.items(),
        ),
    ])

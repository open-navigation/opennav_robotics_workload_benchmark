import os
import subprocess
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context):
    sim_pkg = get_package_share_directory('opennav_benchmark_sim')
    robot_pkg = get_package_share_directory('opennav_benchmark_robot')

    headless_str = LaunchConfiguration('headless').perform(context)
    world_path = LaunchConfiguration('world').perform(context)
    use_rviz = LaunchConfiguration('use_rviz')
    robot_name = LaunchConfiguration('robot_name')
    use_sim_time = LaunchConfiguration('use_sim_time')
    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')
    z_pose = LaunchConfiguration('z_pose')
    yaw = LaunchConfiguration('yaw')

    # Process world xacro to temp SDF synchronously
    world_sdf_temp = tempfile.mktemp(prefix='benchmark_world_', suffix='.sdf')
    xacro_cmd = [
        'xacro', world_path, '-o', world_sdf_temp,
        f'headless:={headless_str}'
    ]
    subprocess.run(xacro_cmd, check=True)

    # Gazebo server
    gz_cmd = ['gz', 'sim', '-r', '-s', world_sdf_temp]
    if headless_str == 'true':
        gz_cmd.insert(3, '--headless-rendering')
    gz_server = ExecuteProcess(
        cmd=gz_cmd,
        output='screen'
    )

    # Gazebo client (GUI) - only if not headless
    gz_client = ExecuteProcess(
        cmd=['gz', 'sim', '-g'],
        output='screen',
        condition=UnlessCondition(LaunchConfiguration('headless'))
    )

    # Include spawn robot launch (handles RSP, bridge, and spawning)
    spawn_robot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(sim_pkg, 'launch', 'spawn_robot.launch.py')
        ),
        launch_arguments={
            'robot_name': robot_name,
            'robot_sdf': os.path.join(robot_pkg, 'urdf', 'benchmark_robot.sdf.xacro'),
            'x_pose': x_pose,
            'y_pose': y_pose,
            'z_pose': z_pose,
            'yaw': yaw,
            'use_sim_time': use_sim_time,
        }.items()
    )

    # RViz
    rviz_config = os.path.join(sim_pkg, 'config', 'benchmark.rviz')
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
        condition=IfCondition(use_rviz),
    )

    # Cleanup temp file on shutdown
    cleanup = RegisterEventHandler(
        OnShutdown(on_shutdown=[
            ExecuteProcess(cmd=['rm', '-f', world_sdf_temp])
        ])
    )

    return [gz_server, gz_client, spawn_robot, rviz, cleanup]


def generate_launch_description():
    sim_pkg = get_package_share_directory('opennav_benchmark_sim')

    declare_headless = DeclareLaunchArgument(
        'headless', default_value='false',
        description='Run Gazebo without GUI client')
    declare_world = DeclareLaunchArgument(
        'world',
        default_value=os.path.join(sim_pkg, 'worlds', 'benchmark_warehouse.sdf.xacro'),
        description='Path to world SDF xacro file')
    declare_robot_name = DeclareLaunchArgument(
        'robot_name', default_value='benchmark_robot',
        description='Name of the robot in simulation')
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation clock')
    declare_x_pose = DeclareLaunchArgument(
        'x_pose', default_value='0.0',
        description='Robot initial X position')
    declare_y_pose = DeclareLaunchArgument(
        'y_pose', default_value='-60.0',
        description='Robot initial Y position')
    declare_z_pose = DeclareLaunchArgument(
        'z_pose', default_value='0.1',
        description='Robot initial Z position')
    declare_yaw = DeclareLaunchArgument(
        'yaw', default_value='1.5708',
        description='Robot initial yaw')
    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Launch RViz for visualization')

    robot_pkg = get_package_share_directory('opennav_benchmark_robot')

    # Set Gazebo resource path so it can resolve package:// URIs for meshes
    set_gz_resource_path = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(sim_pkg, 'worlds'))
    set_gz_resource_path_robot = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.dirname(robot_pkg))

    return LaunchDescription([
        declare_headless,
        declare_world,
        declare_robot_name,
        declare_use_sim_time,
        declare_x_pose,
        declare_y_pose,
        declare_z_pose,
        declare_yaw,
        declare_use_rviz,
        set_gz_resource_path,
        set_gz_resource_path_robot,
        OpaqueFunction(function=launch_setup),
    ])

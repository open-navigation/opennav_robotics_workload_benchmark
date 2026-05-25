import os
import subprocess
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def launch_setup(context):
    sim_pkg = get_package_share_directory('opennav_benchmark_sim')
    robot_pkg = get_package_share_directory('opennav_benchmark_robot')

    robot_name_str = LaunchConfiguration('robot_name').perform(context)
    robot_sdf_path = LaunchConfiguration('robot_sdf').perform(context)
    use_sim_time_str = LaunchConfiguration('use_sim_time').perform(context)
    x_str = LaunchConfiguration('x_pose').perform(context)
    y_str = LaunchConfiguration('y_pose').perform(context)
    z_str = LaunchConfiguration('z_pose').perform(context)
    yaw_str = LaunchConfiguration('yaw').perform(context)
    use_gt_loc = LaunchConfiguration('use_ground_truth_localization')

    # Robot state publisher (URDF for TF)
    robot_urdf_xacro = os.path.join(robot_pkg, 'urdf', 'benchmark_robot.urdf.xacro')
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time_str == 'true',
            'robot_description': ParameterValue(Command(['xacro ', robot_urdf_xacro]), value_type=str),
        }],
    )

    # Process robot SDF xacro synchronously
    robot_sdf_temp = tempfile.mktemp(prefix='benchmark_robot_', suffix='.sdf')
    subprocess.run(
        ['xacro', robot_sdf_path, '-o', robot_sdf_temp, 'namespace:='],
        check=True
    )

    # Spawn robot in Gazebo
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', robot_name_str,
            '-file', robot_sdf_temp,
            '-x', x_str,
            '-y', y_str,
            '-z', z_str,
            '-Y', yaw_str,
        ],
        output='screen'
    )

    # ROS-Gazebo parameter bridge
    bridge_config = os.path.join(sim_pkg, 'config', 'gazebo_bridge.yaml')
    parameter_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{
            'config_file': bridge_config,
            'use_sim_time': use_sim_time_str == 'true',
        }],
        output='screen'
    )

    # Image bridges for cameras (color + depth = 6 bridges)
    camera_front_left_image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera_front_left/image'],
        output='screen'
    )
    camera_front_left_depth_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera_front_left/depth_image'],
        output='screen'
    )
    camera_front_right_image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera_front_right/image'],
        output='screen'
    )
    camera_front_right_depth_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera_front_right/depth_image'],
        output='screen'
    )
    camera_rear_image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera_rear/image'],
        output='screen'
    )
    camera_rear_depth_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera_rear/depth_image'],
        output='screen'
    )

    # Static map->odom TF from spawn pose (perfect localization with zero wheel slip)
    map_to_odom_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='map_to_odom_static_tf',
        arguments=['--x', x_str, '--y', y_str, '--z', '0',
                   '--roll', '0', '--pitch', '0', '--yaw', yaw_str,
                   '--frame-id', 'map', '--child-frame-id', 'odom'],
        condition=IfCondition(use_gt_loc),
    )

    return [
        robot_state_publisher,
        spawn_robot,
        parameter_bridge,
        camera_front_left_image_bridge,
        camera_front_left_depth_bridge,
        camera_front_right_image_bridge,
        camera_front_right_depth_bridge,
        camera_rear_image_bridge,
        camera_rear_depth_bridge,
        map_to_odom_static_tf,
    ]


def generate_launch_description():
    robot_pkg = get_package_share_directory('opennav_benchmark_robot')

    declare_robot_name = DeclareLaunchArgument(
        'robot_name', default_value='benchmark_robot')
    declare_robot_sdf = DeclareLaunchArgument(
        'robot_sdf',
        default_value=os.path.join(robot_pkg, 'urdf', 'benchmark_robot.sdf.xacro'))
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true')
    declare_x_pose = DeclareLaunchArgument('x_pose', default_value='62.6405')
    declare_y_pose = DeclareLaunchArgument('y_pose', default_value='35.9279')
    declare_z_pose = DeclareLaunchArgument('z_pose', default_value='0.1')
    declare_yaw = DeclareLaunchArgument('yaw', default_value='3.151')
    declare_use_gt_loc = DeclareLaunchArgument(
        'use_ground_truth_localization', default_value='true',
        description='Use static map->odom TF from spawn pose instead of AMCL')

    return LaunchDescription([
        declare_robot_name,
        declare_robot_sdf,
        declare_use_sim_time,
        declare_x_pose,
        declare_y_pose,
        declare_z_pose,
        declare_yaw,
        declare_use_gt_loc,
        OpaqueFunction(function=launch_setup),
    ])

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

    base_url = LaunchConfiguration('base_url')
    model = LaunchConfiguration('model')
    default_image_topic = LaunchConfiguration('default_image_topic')

    return LaunchDescription([
        DeclareLaunchArgument(
            'base_url',
            default_value='http://localhost:8080/v1',
            description='Endpoint of the local VLM server.',
        ),
        DeclareLaunchArgument(
            'model',
            default_value='gemma-4',
            description='Model label.',
        ),
        DeclareLaunchArgument(
            'default_image_topic',
            default_value='/camera/rgb/image',
            description='Image topic to use for requests that omit the image field.',
        ),
        Node(
            package='opennav_benchmark_vlm',
            executable='vlm_node',
            name='vlm_node',
            output='screen',
            parameters=[
                params_file,
                {
                    'base_url': base_url,
                    'model': model,
                    'default_image_topic': default_image_topic,
                },
            ],
        ),
    ])

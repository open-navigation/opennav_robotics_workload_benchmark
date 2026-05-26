from setuptools import setup

package_name = 'opennav_benchmark_vlm'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', [
            'config/vlm_params.yaml',
        ]),
        ('share/' + package_name + '/launch', [
            'launch/vlm.launch.py',
        ]),
    ],
    entry_points={
        'console_scripts': [
            'vlm_node = opennav_benchmark_vlm.vlm_node:main',
        ],
    },
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Steve Macenski',
    maintainer_email='steve@opennav.org',
    description='ROS 2 node exposing a locally-served VLM as bool/int/string action servers.',
    license='Apache-2.0',
)

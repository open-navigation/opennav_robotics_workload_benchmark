from setuptools import setup

package_name = 'opennav_benchmark_autonomy'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/maps', [
            'maps/benchmark_warehouse.yaml',
            'maps/benchmark_warehouse.pgm',
        ]),
        ('share/' + package_name + '/annotations', [
            'annotations/warehouse_waypoints.yaml',
        ]),
    ],
    entry_points={
        'console_scripts': [
            'robot_mission_runner = opennav_benchmark_autonomy.robot_mission_runner:main',
        ],
    },
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Steve Macenski',
    maintainer_email='steve@opennav.org',
    description='OpenNav Benchmark Autonomy: maps, annotations, and autonomy scripts',
    license='Apache-2.0',
)

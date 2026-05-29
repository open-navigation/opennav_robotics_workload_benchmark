FROM ros:jazzy-ros-base

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-colcon-common-extensions \
      python3-rosdep \
      python3-pip \
      build-essential \
      ros-jazzy-rmw-cyclonedds-cpp \
      ros-jazzy-rviz2 \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages --no-cache-dir openai

RUN apt-get update \
 && rosdep update --rosdistro jazzy \
 && apt install ros-jazzy-navigation2 ros-jazzy-spatio-temporal-voxel-layer ros-jazzy-nav2-bringup -y

WORKDIR /root/ws
COPY opennav_benchmark_robotics_workload/opennav_benchmark_mission_dispatcher/  src/opennav_benchmark_mission_dispatcher/
COPY opennav_benchmark_robotics_workload/opennav_benchmark_nav2/         src/opennav_benchmark_nav2/
COPY opennav_benchmark_simulation/opennav_benchmark_robot/  src/opennav_benchmark_robot/
COPY opennav_benchmark_ai_workload/opennav_benchmark_vlm/       src/opennav_benchmark_vlm/
COPY opennav_benchmark_ai_workload/opennav_benchmark_vlm_msgs/  src/opennav_benchmark_vlm_msgs/
COPY opennav_benchmark_ai_workload/opennav_benchmark_vlm_bt/    src/opennav_benchmark_vlm_bt/

RUN rosdep install --from-paths src --ignore-src -y --rosdistro jazzy \
 && rm -rf /var/lib/apt/lists/* \
 && . /opt/ros/jazzy/setup.sh \
 && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# Default = single-machine localhost discovery.
# For HIL (sim on one machine, autonomy on another), swap to cyclonedds_hil.xml
# and edit its <NetworkInterface address="..."> to match your LAN subnet.
COPY opennav_benchmark_pipeline/docker/robotic_amr_workload/cyclonedds_localhost.xml \
     /opt/opennav/cyclonedds.xml
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV CYCLONEDDS_URI=file:///opt/opennav/cyclonedds.xml

COPY opennav_benchmark_pipeline/docker/robotic_amr_workload/entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh
CMD ["ros2", "launch", "opennav_benchmark_mission_dispatcher", "benchmark_application.launch.py"]

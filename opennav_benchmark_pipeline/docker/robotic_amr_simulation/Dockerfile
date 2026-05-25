FROM ros:jazzy-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-colcon-common-extensions \
      python3-rosdep \
      build-essential \
      ros-jazzy-rmw-cyclonedds-cpp \
      ros-jazzy-ros-gz \
      ros-jazzy-ros-gz-bridge \
      ros-jazzy-ros-gz-image \
      ros-jazzy-ros-gz-interfaces \
      ros-jazzy-ros-gz-sim \
      ros-jazzy-robot-state-publisher \
      ros-jazzy-joint-state-publisher \
      ros-jazzy-xacro \
      ros-jazzy-rviz2 \
      libgl1-mesa-dri \
      mesa-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /root/ws
COPY opennav_benchmark_simulation/opennav_benchmark_sim/    src/opennav_benchmark_sim/
COPY opennav_benchmark_simulation/opennav_benchmark_robot/  src/opennav_benchmark_robot/

RUN apt-get update \
 && rosdep update --rosdistro jazzy \
 && rosdep install --from-paths src --ignore-src -y --rosdistro jazzy \
 && rm -rf /var/lib/apt/lists/* \
 && . /opt/ros/jazzy/setup.sh \
 && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# Default = single-machine localhost discovery.
# For HIL (sim on one machine, autonomy on another), swap to cyclonedds_hil.xml
# and edit its <NetworkInterface address="..."> to match your LAN subnet.
COPY opennav_benchmark_pipeline/docker/robotic_amr_simulation/cyclonedds_localhost.xml \
     /opt/opennav/cyclonedds.xml
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV CYCLONEDDS_URI=file:///opt/opennav/cyclonedds.xml

ENV GZ_SIM_RESOURCE_PATH=/root/ws/install/opennav_benchmark_sim/share/opennav_benchmark_sim/worlds:/root/ws/install/opennav_benchmark_sim/share/opennav_benchmark_sim/models:/root/ws/install/opennav_benchmark_robot/share

COPY opennav_benchmark_pipeline/docker/robotic_amr_simulation/entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh
CMD ["ros2", "launch", "opennav_benchmark_sim", "simulation_simplified.launch.py", "headless:=false"]

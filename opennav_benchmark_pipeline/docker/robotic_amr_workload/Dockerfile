FROM ros:jazzy-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-nav2-bringup \
      ros-jazzy-nav2-loopback-sim \
      ros-jazzy-nav2-minimal-tb4-sim \
      ros-jazzy-rviz2 \
      ros-jazzy-turtlebot4-navigation \
      ros-jazzy-rmw-cyclonedds-cpp \
 && rm -rf /var/lib/apt/lists/*

# Default = single-machine localhost discovery.
# For HIL (sim on one machine, autonomy on another), swap to cyclonedds_hil.xml
# and edit its <NetworkInterface address="..."> to match your LAN subnet.
COPY cyclonedds_localhost.xml /opt/opennav/cyclonedds.xml
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV CYCLONEDDS_URI=file:///opt/opennav/cyclonedds.xml

CMD ["ros2", "launch", "nav2_bringup", "tb4_loopback_simulation.launch.py", "headless:=False"]

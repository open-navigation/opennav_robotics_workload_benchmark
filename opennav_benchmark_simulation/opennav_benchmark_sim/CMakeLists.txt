cmake_minimum_required(VERSION 3.8)
project(opennav_benchmark_sim)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch models scripts test worlds
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS test/visualize_waypoints.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

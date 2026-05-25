cmake_minimum_required(VERSION 3.8)
project(opennav_benchmark_vlm_bt)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(behaviortree_cpp REQUIRED)
find_package(nav2_behavior_tree REQUIRED)
find_package(nav2_util REQUIRED)
find_package(opennav_benchmark_vlm_msgs REQUIRED)

set(dependencies
  rclcpp
  rclcpp_action
  sensor_msgs
  behaviortree_cpp
  nav2_behavior_tree
  nav2_util
  opennav_benchmark_vlm_msgs
)

include_directories(include)

# Action plugins
add_library(vlm_query_bool_action_bt_node SHARED src/query_bool_action.cpp)
list(APPEND plugin_libs vlm_query_bool_action_bt_node)

add_library(vlm_query_int_action_bt_node SHARED src/query_int_action.cpp)
list(APPEND plugin_libs vlm_query_int_action_bt_node)

add_library(vlm_query_string_action_bt_node SHARED src/query_string_action.cpp)
list(APPEND plugin_libs vlm_query_string_action_bt_node)

# Condition plugins
add_library(vlm_check_bool_bt_node SHARED src/check_bool.cpp)
list(APPEND plugin_libs vlm_check_bool_bt_node)

# Utility plugins
add_library(vlm_mark_lethal_ahead_bt_node SHARED src/mark_lethal_ahead.cpp)
list(APPEND plugin_libs vlm_mark_lethal_ahead_bt_node)

# Cancel plugins
add_library(vlm_cancel_query_bool_bt_node SHARED src/cancel_query_bool.cpp)
list(APPEND plugin_libs vlm_cancel_query_bool_bt_node)

add_library(vlm_cancel_query_int_bt_node SHARED src/cancel_query_int.cpp)
list(APPEND plugin_libs vlm_cancel_query_int_bt_node)

add_library(vlm_cancel_query_string_bt_node SHARED src/cancel_query_string.cpp)
list(APPEND plugin_libs vlm_cancel_query_string_bt_node)

foreach(bt_plugin ${plugin_libs})
  ament_target_dependencies(${bt_plugin} ${dependencies})
  target_compile_definitions(${bt_plugin} PRIVATE BT_PLUGIN_EXPORT)
endforeach()

install(TARGETS ${plugin_libs}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY include/
  DESTINATION include/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_query_bool_action test/test_query_bool_action.cpp)
  target_link_libraries(test_query_bool_action vlm_query_bool_action_bt_node)
  ament_target_dependencies(test_query_bool_action ${dependencies})

  ament_add_gtest(test_query_int_action test/test_query_int_action.cpp)
  target_link_libraries(test_query_int_action vlm_query_int_action_bt_node)
  ament_target_dependencies(test_query_int_action ${dependencies})

  ament_add_gtest(test_query_string_action test/test_query_string_action.cpp)
  target_link_libraries(test_query_string_action vlm_query_string_action_bt_node)
  ament_target_dependencies(test_query_string_action ${dependencies})

  ament_add_gtest(test_cancel_query_bool test/test_cancel_query_bool.cpp)
  target_link_libraries(test_cancel_query_bool vlm_cancel_query_bool_bt_node)
  ament_target_dependencies(test_cancel_query_bool ${dependencies})

  ament_add_gtest(test_cancel_query_int test/test_cancel_query_int.cpp)
  target_link_libraries(test_cancel_query_int vlm_cancel_query_int_bt_node)
  ament_target_dependencies(test_cancel_query_int ${dependencies})

  ament_add_gtest(test_cancel_query_string test/test_cancel_query_string.cpp)
  target_link_libraries(test_cancel_query_string vlm_cancel_query_string_bt_node)
  ament_target_dependencies(test_cancel_query_string ${dependencies})
endif()

ament_export_include_directories(include)
ament_export_libraries(${plugin_libs})
ament_export_dependencies(${dependencies})

ament_package()

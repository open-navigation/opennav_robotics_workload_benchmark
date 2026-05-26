// Copyright (c) 2026 Open Navigation LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <memory>
#include <string>

#include "opennav_benchmark_vlm_bt/mark_lethal_ahead.hpp"

namespace opennav_benchmark_vlm_bt
{

MarkLethalAhead::MarkLethalAhead(
  const std::string & name, const BT::NodeConfiguration & config)
: BT::SyncActionNode(name, config),
  last_publish_time_(rclcpp::Time(0, 0, RCL_ROS_TIME))
{
}

BT::NodeStatus MarkLethalAhead::tick()
{
  // Initialize publisher on first tick
  if (!publisher_) {
    auto node = config().blackboard->get<rclcpp::Node::SharedPtr>("node");
    std::string topic = "/vlm_virtual_obstacles";
    getInput("topic", topic);
    publisher_ = node->create_publisher<sensor_msgs::msg::PointCloud2>(topic, 10);
    clock_ = node->get_clock();
  }

  // Check cooldown
  double cooldown = 10.0;
  getInput("cooldown", cooldown);
  auto now = clock_->now();
  if ((now - last_publish_time_).seconds() < cooldown) {
    return BT::NodeStatus::SUCCESS;
  }

  // Get parameters
  double distance = 2.0;
  double width = 1.2;
  double depth = 0.3;
  double height = 0.5;
  getInput("distance", distance);
  getInput("width", width);
  getInput("depth", depth);
  getInput("height", height);

  // Generate point cloud in base_link frame
  const double spacing = 0.05;
  int num_x = static_cast<int>(depth / spacing) + 1;
  int num_y = static_cast<int>(width / spacing) + 1;
  int num_points = num_x * num_y;

  auto cloud = std::make_unique<sensor_msgs::msg::PointCloud2>();
  cloud->header.frame_id = "base_link";
  cloud->header.stamp = clock_->now();
  cloud->height = 1;
  cloud->width = num_points;
  cloud->is_dense = true;
  cloud->is_bigendian = false;

  sensor_msgs::PointCloud2Modifier modifier(*cloud);
  modifier.setPointCloud2FieldsByString(1, "xyz");
  modifier.resize(num_points);

  sensor_msgs::PointCloud2Iterator<float> iter_x(*cloud, "x");
  sensor_msgs::PointCloud2Iterator<float> iter_y(*cloud, "y");
  sensor_msgs::PointCloud2Iterator<float> iter_z(*cloud, "z");

  double x_start = distance - depth / 2.0;
  double y_start = -width / 2.0;

  for (int ix = 0; ix < num_x; ++ix) {
    for (int iy = 0; iy < num_y; ++iy) {
      *iter_x = static_cast<float>(x_start + ix * spacing);
      *iter_y = static_cast<float>(y_start + iy * spacing);
      *iter_z = static_cast<float>(height);
      ++iter_x;
      ++iter_y;
      ++iter_z;
    }
  }

  publisher_->publish(std::move(cloud));
  last_publish_time_ = now;
  return BT::NodeStatus::SUCCESS;
}

}  // namespace opennav_benchmark_vlm_bt

#include "behaviortree_cpp/bt_factory.h"
BT_REGISTER_NODES(factory)
{
  factory.registerNodeType<opennav_benchmark_vlm_bt::MarkLethalAhead>("MarkLethalAhead");
}

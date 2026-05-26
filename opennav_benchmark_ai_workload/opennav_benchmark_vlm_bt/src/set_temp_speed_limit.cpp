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

#include "opennav_benchmark_vlm_bt/set_temp_speed_limit.hpp"

namespace opennav_benchmark_vlm_bt
{

SetTempSpeedLimit::SetTempSpeedLimit(
  const std::string & name, const BT::NodeConfiguration & config)
: BT::SyncActionNode(name, config),
  last_trigger_time_(rclcpp::Time(0, 0, RCL_ROS_TIME)),
  speed_limited_(false)
{
}

BT::NodeStatus SetTempSpeedLimit::tick()
{
  // Initialize publisher on first tick
  if (!publisher_) {
    auto node = config().blackboard->get<rclcpp::Node::SharedPtr>("node");
    std::string topic = "/speed_limit";
    getInput("topic", topic);
    publisher_ = node->create_publisher<nav2_msgs::msg::SpeedLimit>(topic, 10);
    clock_ = node->get_clock();
  }

  bool is_active = false;
  getInput("is_active", is_active);

  if (is_active) {
    // Condition is active: reset timer and set speed limit if not already set
    last_trigger_time_ = clock_->now();
    if (!speed_limited_) {
      double limit = 50.0;
      getInput("speed_limit", limit);
      nav2_msgs::msg::SpeedLimit msg;
      msg.percentage = true;
      msg.speed_limit = limit;
      publisher_->publish(msg);
      speed_limited_ = true;
    }
  } else if (speed_limited_) {
    // Condition is inactive but speed is still limited: check if duration elapsed
    double duration = 5.0;
    getInput("duration", duration);
    auto now = clock_->now();
    if ((now - last_trigger_time_).seconds() > duration) {
      nav2_msgs::msg::SpeedLimit msg;
      msg.percentage = true;
      msg.speed_limit = 0.0;
      publisher_->publish(msg);
      speed_limited_ = false;
    }
  }

  return BT::NodeStatus::SUCCESS;
}

}  // namespace opennav_benchmark_vlm_bt

#include "behaviortree_cpp/bt_factory.h"
BT_REGISTER_NODES(factory)
{
  factory.registerNodeType<opennav_benchmark_vlm_bt::SetTempSpeedLimit>("SetTempSpeedLimit");
}

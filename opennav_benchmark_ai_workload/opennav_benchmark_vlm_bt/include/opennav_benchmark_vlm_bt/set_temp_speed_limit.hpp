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

#ifndef OPENNAV_BENCHMARK_VLM_BT__SET_TEMP_SPEED_LIMIT_HPP_
#define OPENNAV_BENCHMARK_VLM_BT__SET_TEMP_SPEED_LIMIT_HPP_

#include <string>

#include "behaviortree_cpp/action_node.h"
#include "rclcpp/rclcpp.hpp"
#include "nav2_msgs/msg/speed_limit.hpp"

namespace opennav_benchmark_vlm_bt
{

/**
 * @class SetTempSpeedLimit
 * @brief BT sync action node that publishes a temporary speed limit via the
 * Nav2 speed_limit topic. When the triggering condition is active, it sets
 * the speed limit and resets an internal timer. When the condition becomes
 * inactive, the speed limit persists until the configured duration elapses,
 * then full speed is restored. Only publishes on state transitions to avoid
 * flooding the topic.
 */
class SetTempSpeedLimit : public BT::SyncActionNode
{
public:
  /**
   * @brief Constructor
   * @param name Name of the XML tag for this node
   * @param config BT node configuration
   */
  SetTempSpeedLimit(const std::string & name, const BT::NodeConfiguration & config);

  /**
   * @brief Manages speed limit state based on the is_active input
   * @return SUCCESS always
   */
  BT::NodeStatus tick() override;

  /**
   * @brief Creates list of BT ports
   * @return BT::PortsList containing configuration input ports
   */
  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<double>("speed_limit", 50.0, "Speed limit percentage of max speed"),
      BT::InputPort<double>("duration", 5.0, "Seconds to maintain limit after last trigger"),
      BT::InputPort<std::string>("topic", "/speed_limit", "Topic to publish SpeedLimit on"),
      BT::InputPort<bool>("is_active", "Whether the triggering condition is currently active"),
    };
  }

private:
  rclcpp::Publisher<nav2_msgs::msg::SpeedLimit>::SharedPtr publisher_;
  rclcpp::Clock::SharedPtr clock_;
  rclcpp::Time last_trigger_time_;
  bool speed_limited_;
};

}  // namespace opennav_benchmark_vlm_bt

#endif  // OPENNAV_BENCHMARK_VLM_BT__SET_TEMP_SPEED_LIMIT_HPP_

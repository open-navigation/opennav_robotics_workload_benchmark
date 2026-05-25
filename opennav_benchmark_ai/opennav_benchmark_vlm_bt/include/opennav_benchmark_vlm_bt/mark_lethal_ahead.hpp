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

#ifndef OPENNAV_BENCHMARK_VLM_BT__MARK_LETHAL_AHEAD_HPP_
#define OPENNAV_BENCHMARK_VLM_BT__MARK_LETHAL_AHEAD_HPP_

#include <string>

#include "behaviortree_cpp/action_node.h"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "sensor_msgs/point_cloud2_iterator.hpp"

namespace opennav_benchmark_vlm_bt
{

/**
 * @class MarkLethalAhead
 * @brief BT sync action node that publishes a PointCloud2 grid of virtual obstacle
 * points in front of the robot to mark the area as lethal in costmaps. Includes a
 * cooldown timer to prevent repeated marking while the robot navigates away from
 * a previously detected hazard. Points are published in the base_link frame and
 * the costmap handles the TF transform.
 */
class MarkLethalAhead : public BT::SyncActionNode
{
public:
  /**
   * @brief Constructor
   * @param name Name of the XML tag for this node
   * @param config BT node configuration
   */
  MarkLethalAhead(const std::string & name, const BT::NodeConfiguration & config);

  /**
   * @brief Publishes a PointCloud2 obstacle wall in front of the robot if cooldown has elapsed
   * @return SUCCESS always (cooldown skip or successful publish)
   */
  BT::NodeStatus tick() override;

  /**
   * @brief Creates list of BT ports
   * @return BT::PortsList containing configuration input ports
   */
  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<double>("distance", 2.0, "Distance ahead to place obstacle center (m)"),
      BT::InputPort<double>("width", 1.2, "Lateral width of virtual obstacle (m)"),
      BT::InputPort<double>("depth", 0.3, "Longitudinal depth of virtual obstacle (m)"),
      BT::InputPort<double>("height", 0.5, "Height of points above ground (m)"),
      BT::InputPort<std::string>("topic", "/vlm_virtual_obstacles", "Topic to publish on"),
      BT::InputPort<double>("cooldown", 10.0, "Minimum seconds between publishes"),
    };
  }

private:
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr publisher_;
  rclcpp::Clock::SharedPtr clock_;
  rclcpp::Time last_publish_time_;
};

}  // namespace opennav_benchmark_vlm_bt

#endif  // OPENNAV_BENCHMARK_VLM_BT__MARK_LETHAL_AHEAD_HPP_

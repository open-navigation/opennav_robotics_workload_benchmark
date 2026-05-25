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

#ifndef OPENNAV_BENCHMARK_VLM_BT__CANCEL_QUERY_INT_HPP_
#define OPENNAV_BENCHMARK_VLM_BT__CANCEL_QUERY_INT_HPP_

#include <string>

#include "opennav_benchmark_vlm_msgs/action/query_int.hpp"
#include "nav2_behavior_tree/bt_cancel_action_node.hpp"

namespace opennav_benchmark_vlm_bt
{

/**
 * @class CancelQueryInt
 * @brief BT node to cancel an in-flight QueryInt VLM action request.
 */
class CancelQueryInt
  : public nav2_behavior_tree::BtCancelActionNode<opennav_benchmark_vlm_msgs::action::QueryInt>
{
public:
  /**
   * @brief Constructor
   * @param xml_tag_name Name of the XML tag for this node
   * @param action_name ROS 2 action server name
   * @param conf BT node configuration
   */
  CancelQueryInt(
    const std::string & xml_tag_name,
    const std::string & action_name,
    const BT::NodeConfiguration & conf);

  /**
   * @brief Creates list of BT ports
   * @return Empty BT::PortsList
   */
  static BT::PortsList providedPorts()
  {
    return providedBasicPorts({});
  }
};

}  // namespace opennav_benchmark_vlm_bt

#endif  // OPENNAV_BENCHMARK_VLM_BT__CANCEL_QUERY_INT_HPP_

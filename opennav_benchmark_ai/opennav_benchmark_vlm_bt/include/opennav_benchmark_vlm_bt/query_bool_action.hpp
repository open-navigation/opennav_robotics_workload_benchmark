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

#ifndef OPENNAV_BENCHMARK_VLM_BT__QUERY_BOOL_ACTION_HPP_
#define OPENNAV_BENCHMARK_VLM_BT__QUERY_BOOL_ACTION_HPP_

#include <string>

#include "opennav_benchmark_vlm_msgs/action/query_bool.hpp"
#include "nav2_behavior_tree/bt_action_node.hpp"

namespace opennav_benchmark_vlm_bt
{

class QueryBoolAction
  : public nav2_behavior_tree::BtActionNode<opennav_benchmark_vlm_msgs::action::QueryBool>
{
  using Action = opennav_benchmark_vlm_msgs::action::QueryBool;

public:
  QueryBoolAction(
    const std::string & xml_tag_name,
    const std::string & action_name,
    const BT::NodeConfiguration & conf);

  void on_tick() override;
  BT::NodeStatus on_success() override;
  BT::NodeStatus on_aborted() override;
  BT::NodeStatus on_cancelled() override;

  static BT::PortsList providedPorts()
  {
    return providedBasicPorts(
      {
        BT::InputPort<std::string>("prompt", "Prompt to send to VLM"),
        BT::InputPort<sensor_msgs::msg::Image>("image", "Image to send to VLM"),
        BT::OutputPort<bool>("value", "Boolean result from VLM"),
        BT::OutputPort<bool>("success", "Whether the VLM query succeeded"),
      });
  }
};

}  // namespace opennav_benchmark_vlm_bt

#endif  // OPENNAV_BENCHMARK_VLM_BT__QUERY_BOOL_ACTION_HPP_

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

#include <string>
#include <memory>

#include "opennav_benchmark_vlm_bt/query_bool_action.hpp"

namespace opennav_benchmark_vlm_bt
{

QueryBoolAction::QueryBoolAction(
  const std::string & xml_tag_name,
  const std::string & action_name,
  const BT::NodeConfiguration & conf)
: BtActionNode<opennav_benchmark_vlm_msgs::action::QueryBool>(xml_tag_name, action_name, conf)
{
}

void QueryBoolAction::on_tick()
{
  getInput("prompt", goal_.prompt);
  sensor_msgs::msg::Image image;
  if (getInput("image", image)) {
    goal_.image = image;
  }
}

BT::NodeStatus QueryBoolAction::on_success()
{
  setOutput("value", result_.result->value);
  setOutput("success", result_.result->success);
  return result_.result->success ? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
}

BT::NodeStatus QueryBoolAction::on_aborted()
{
  return BT::NodeStatus::FAILURE;
}

BT::NodeStatus QueryBoolAction::on_cancelled()
{
  return BT::NodeStatus::SUCCESS;
}

}  // namespace opennav_benchmark_vlm_bt

#include "behaviortree_cpp/bt_factory.h"
BT_REGISTER_NODES(factory)
{
  BT::NodeBuilder builder =
    [](const std::string & name, const BT::NodeConfiguration & config)
    {
      return std::make_unique<opennav_benchmark_vlm_bt::QueryBoolAction>(
        name, "vlm_node/query_bool", config);
    };

  factory.registerBuilder<opennav_benchmark_vlm_bt::QueryBoolAction>("QueryBool", builder);
}

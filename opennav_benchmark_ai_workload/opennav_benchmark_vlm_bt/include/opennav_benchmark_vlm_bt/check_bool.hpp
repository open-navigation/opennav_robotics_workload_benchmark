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

#ifndef OPENNAV_BENCHMARK_VLM_BT__CHECK_BOOL_HPP_
#define OPENNAV_BENCHMARK_VLM_BT__CHECK_BOOL_HPP_

#include <string>

#include "behaviortree_cpp/condition_node.h"

namespace opennav_benchmark_vlm_bt
{

/**
 * @class CheckBool
 * @brief BT condition node that checks a boolean blackboard value.
 * Returns SUCCESS if the value is true, FAILURE otherwise.
 */
class CheckBool : public BT::ConditionNode
{
public:
  /**
   * @brief Constructor
   * @param name Name of the XML tag for this node
   * @param config BT node configuration
   */
  CheckBool(const std::string & name, const BT::NodeConfiguration & config);

  /**
   * @brief Checks the boolean input port value
   * @return SUCCESS if value is true, FAILURE otherwise
   */
  BT::NodeStatus tick() override;

  /**
   * @brief Creates list of BT ports
   * @return BT::PortsList containing the boolean input port
   */
  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<bool>("value", "Boolean value to check"),
    };
  }
};

}  // namespace opennav_benchmark_vlm_bt

#endif  // OPENNAV_BENCHMARK_VLM_BT__CHECK_BOOL_HPP_

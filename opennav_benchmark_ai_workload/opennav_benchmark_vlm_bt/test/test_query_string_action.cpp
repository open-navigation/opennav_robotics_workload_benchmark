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

#include <gtest/gtest.h>
#include <memory>
#include <string>
#include <thread>

#include "behaviortree_cpp/bt_factory.h"
#include "nav2_behavior_tree/utils/test_action_server.hpp"
#include "opennav_benchmark_vlm_bt/query_string_action.hpp"

using Action = opennav_benchmark_vlm_msgs::action::QueryString;

class QueryStringActionServer : public TestActionServer<Action>
{
public:
  QueryStringActionServer()
  : TestActionServer("vlm_node/query_string")
  {}

protected:
  void execute(
    const std::shared_ptr<rclcpp_action::ServerGoalHandle<Action>> goal_handle) override
  {
    auto result = std::make_shared<Action::Result>();
    if (getReturnSuccess()) {
      result->value = "a red ball";
      result->success = true;
      goal_handle->succeed(result);
    } else {
      goal_handle->abort(result);
    }
  }
};

class QueryStringActionTestFixture : public ::testing::Test
{
public:
  static void SetUpTestCase()
  {
    node_ = std::make_shared<rclcpp::Node>("query_string_action_test_fixture");
    factory_ = std::make_shared<BT::BehaviorTreeFactory>();

    config_ = new BT::NodeConfiguration();
    config_->blackboard = BT::Blackboard::create();
    config_->blackboard->set("node", node_);
    config_->blackboard->set<std::chrono::milliseconds>(
      "server_timeout", std::chrono::milliseconds(20));
    config_->blackboard->set<std::chrono::milliseconds>(
      "bt_loop_duration", std::chrono::milliseconds(10));
    config_->blackboard->set<std::chrono::milliseconds>(
      "wait_for_service_timeout", std::chrono::milliseconds(1000));

    BT::NodeBuilder builder =
      [](const std::string & name, const BT::NodeConfiguration & config)
      {
        return std::make_unique<opennav_benchmark_vlm_bt::QueryStringAction>(
          name, "vlm_node/query_string", config);
      };

    factory_->registerBuilder<opennav_benchmark_vlm_bt::QueryStringAction>(
      "QueryString", builder);
  }

  static void TearDownTestCase()
  {
    delete config_;
    config_ = nullptr;
    node_.reset();
    action_server_.reset();
    factory_.reset();
  }

  void TearDown() override
  {
    tree_.reset();
  }

  static std::shared_ptr<QueryStringActionServer> action_server_;

protected:
  static rclcpp::Node::SharedPtr node_;
  static BT::NodeConfiguration * config_;
  static std::shared_ptr<BT::BehaviorTreeFactory> factory_;
  static std::shared_ptr<BT::Tree> tree_;
};

rclcpp::Node::SharedPtr QueryStringActionTestFixture::node_ = nullptr;
std::shared_ptr<QueryStringActionServer>
QueryStringActionTestFixture::action_server_ = nullptr;
BT::NodeConfiguration * QueryStringActionTestFixture::config_ = nullptr;
std::shared_ptr<BT::BehaviorTreeFactory>
QueryStringActionTestFixture::factory_ = nullptr;
std::shared_ptr<BT::Tree> QueryStringActionTestFixture::tree_ = nullptr;

TEST_F(QueryStringActionTestFixture, test_ports)
{
  std::string xml_txt =
    R"(
      <root BTCPP_format="4">
        <BehaviorTree ID="MainTree">
            <QueryString prompt="What do you see?" />
        </BehaviorTree>
      </root>)";

  tree_ = std::make_shared<BT::Tree>(
    factory_->createTreeFromText(xml_txt, config_->blackboard));
  EXPECT_EQ(tree_->rootNode()->getInput<std::string>("prompt"), "What do you see?");
}

TEST_F(QueryStringActionTestFixture, test_tick)
{
  std::string xml_txt =
    R"(
      <root BTCPP_format="4">
        <BehaviorTree ID="MainTree">
            <QueryString prompt="What do you see?" value="{vlm_str}" success="{vlm_success}" />
        </BehaviorTree>
      </root>)";

  tree_ = std::make_shared<BT::Tree>(
    factory_->createTreeFromText(xml_txt, config_->blackboard));

  while (tree_->rootNode()->status() != BT::NodeStatus::SUCCESS) {
    tree_->rootNode()->executeTick();
  }

  EXPECT_EQ(tree_->rootNode()->status(), BT::NodeStatus::SUCCESS);
  EXPECT_EQ(action_server_->getCurrentGoal()->prompt, "What do you see?");
}

TEST_F(QueryStringActionTestFixture, test_tick_abort)
{
  std::string xml_txt =
    R"(
      <root BTCPP_format="4">
        <BehaviorTree ID="MainTree">
            <QueryString prompt="What do you see?" />
        </BehaviorTree>
      </root>)";

  action_server_->setReturnSuccess(false);
  tree_ = std::make_shared<BT::Tree>(
    factory_->createTreeFromText(xml_txt, config_->blackboard));

  while (tree_->rootNode()->status() != BT::NodeStatus::SUCCESS &&
    tree_->rootNode()->status() != BT::NodeStatus::FAILURE)
  {
    tree_->rootNode()->executeTick();
  }

  EXPECT_EQ(tree_->rootNode()->status(), BT::NodeStatus::FAILURE);
  action_server_->setReturnSuccess(true);
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);

  rclcpp::init(argc, argv);

  QueryStringActionTestFixture::action_server_ =
    std::make_shared<QueryStringActionServer>();
  std::thread server_thread([]() {
      rclcpp::spin(QueryStringActionTestFixture::action_server_);
    });

  int all_successful = RUN_ALL_TESTS();

  rclcpp::shutdown();
  server_thread.join();

  return all_successful;
}

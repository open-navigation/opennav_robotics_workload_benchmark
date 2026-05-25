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
#include "opennav_benchmark_vlm_bt/cancel_query_string.hpp"

using Action = opennav_benchmark_vlm_msgs::action::QueryString;

class CancelQueryStringServer : public TestActionServer<Action>
{
public:
  CancelQueryStringServer()
  : TestActionServer("vlm_node/query_string")
  {}

protected:
  void execute(
    const std::shared_ptr<rclcpp_action::ServerGoalHandle<Action>> goal_handle) override
  {
    while (!goal_handle->is_canceling()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(15));
    }
  }
};

class CancelQueryStringTestFixture : public ::testing::Test
{
public:
  static void SetUpTestCase()
  {
    node_ = std::make_shared<rclcpp::Node>("cancel_query_string_test_fixture");
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

    client_ = rclcpp_action::create_client<Action>(node_, "vlm_node/query_string");

    BT::NodeBuilder builder =
      [](const std::string & name, const BT::NodeConfiguration & config)
      {
        return std::make_unique<opennav_benchmark_vlm_bt::CancelQueryString>(
          name, "vlm_node/query_string", config);
      };

    factory_->registerBuilder<opennav_benchmark_vlm_bt::CancelQueryString>(
      "CancelQueryString", builder);
  }

  static void TearDownTestCase()
  {
    delete config_;
    config_ = nullptr;
    node_.reset();
    action_server_.reset();
    client_.reset();
    factory_.reset();
  }

  void TearDown() override
  {
    tree_.reset();
  }

  static std::shared_ptr<CancelQueryStringServer> action_server_;
  static std::shared_ptr<rclcpp_action::Client<Action>> client_;

protected:
  static rclcpp::Node::SharedPtr node_;
  static BT::NodeConfiguration * config_;
  static std::shared_ptr<BT::BehaviorTreeFactory> factory_;
  static std::shared_ptr<BT::Tree> tree_;
};

rclcpp::Node::SharedPtr CancelQueryStringTestFixture::node_ = nullptr;
std::shared_ptr<CancelQueryStringServer>
CancelQueryStringTestFixture::action_server_ = nullptr;
std::shared_ptr<rclcpp_action::Client<Action>>
CancelQueryStringTestFixture::client_ = nullptr;
BT::NodeConfiguration * CancelQueryStringTestFixture::config_ = nullptr;
std::shared_ptr<BT::BehaviorTreeFactory>
CancelQueryStringTestFixture::factory_ = nullptr;
std::shared_ptr<BT::Tree> CancelQueryStringTestFixture::tree_ = nullptr;

TEST_F(CancelQueryStringTestFixture, test_ports)
{
  std::string xml_txt =
    R"(
      <root BTCPP_format="4">
        <BehaviorTree ID="MainTree">
             <CancelQueryString name="CancelQueryString"/>
        </BehaviorTree>
      </root>)";

  tree_ = std::make_shared<BT::Tree>(
    factory_->createTreeFromText(xml_txt, config_->blackboard));

  auto goal_msg = Action::Goal();
  goal_msg.prompt = "What do you see?";

  client_->wait_for_action_server();
  client_->async_send_goal(goal_msg);

  std::this_thread::sleep_for(std::chrono::milliseconds(15));

  tree_->rootNode()->executeTick();

  EXPECT_EQ(tree_->rootNode()->status(), BT::NodeStatus::SUCCESS);
  EXPECT_EQ(action_server_->isGoalCancelled(), true);
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);

  rclcpp::init(argc, argv);

  CancelQueryStringTestFixture::action_server_ =
    std::make_shared<CancelQueryStringServer>();
  std::thread server_thread([]() {
      rclcpp::spin(CancelQueryStringTestFixture::action_server_);
    });

  int all_successful = RUN_ALL_TESTS();

  rclcpp::shutdown();
  server_thread.join();

  return all_successful;
}

import threading

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from rclpy.time import Time

from sensor_msgs.msg import Image

from opennav_benchmark_vlm_msgs.action import QueryBool, QueryInt, QueryString

from opennav_benchmark_vlm.image_utils import encode_image, is_image_empty
from opennav_benchmark_vlm.output_parser import BoolParser, IntParser, StringParser
from opennav_benchmark_vlm.vlm_client import VLMClient


class VLMNode(Node):
    """Hosts action servers backed by a locally-served VLM."""

    def __init__(self):
        """Declare parameters, build the VLM client, subscribe to image, and start the action servers."""
        super().__init__('vlm_node')

        self.declare_parameter('base_url', 'http://localhost:8080/v1')
        self.declare_parameter('api_key', 'EMPTY')
        self.declare_parameter('model', 'gemma-4')
        self.declare_parameter('temperature', 1.0)
        self.declare_parameter('max_tokens', 256)
        self.declare_parameter('request_timeout', 30.0)
        self.declare_parameter('max_retries', 3)
        self.declare_parameter('executor_threads', 4)
        self.declare_parameter('default_image_topic', '/camera/rgb/image')
        self.declare_parameter('max_image_age', 1.0)
        self.declare_parameter(
            'system_prompt',
            'You are the perception assistant for a mobile robot operating in an active '
            'warehouse, observing through the robot\'s onboard camera. Answer questions '
            'about the scene from the robot\'s point of view: what is present, what is '
            'happening, and what might affect the robot\'s ability to operate safely or '
            'make progress.\n\n'
            'Pay particular attention to:\n'
            '- People and their activity (working, walking, blocking aisles, gathered)\n'
            '- Warehouse vehicles: forklifts, pallet jacks, other AMRs, hand trucks\n'
            '- Floor hazards: spills, liquids, debris, fallen product, loose packaging, '
            'straps, cords, stray pallets, broken bottles, small objects\n'
            '- Obstructions: closed doors, gates, barriers, cones, parked equipment, '
            'overhanging loads, racking damage\n'
            '- Visibility and environment: low light, glare, dust, signage, lane markings\n\n'
            'Base every answer only on what is actually visible in the image. Do not '
            'speculate beyond what you can see. If you are not sure, say so rather than '
            'guessing. Accuracy matters more than completeness, and "unknown" is a '
            'valid and useful answer.',
        )

        self._client = VLMClient(
            base_url=self.get_parameter('base_url').value,
            api_key=self.get_parameter('api_key').value,
            model=self.get_parameter('model').value,
            temperature=float(self.get_parameter('temperature').value),
            max_tokens=int(self.get_parameter('max_tokens').value),
        )
        self._request_timeout = float(self.get_parameter('request_timeout').value)
        self._max_retries = max(1, int(self.get_parameter('max_retries').value))
        self._max_image_age = float(self.get_parameter('max_image_age').value)
        self._system_prompt = self.get_parameter('system_prompt').value

        self._latest_image = None
        self._image_lock = threading.Lock()

        topic = self.get_parameter('default_image_topic').value
        if topic:
            qos = QoSProfile(
                reliability=QoSReliabilityPolicy.BEST_EFFORT,
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=1,
            )
            self._image_sub = self.create_subscription(
                Image, topic, self._on_image, qos)
            self.get_logger().info(f'Subscribed to image topic: {topic}')
        else:
            self._image_sub = None
            self.get_logger().info('No default_image_topic; subscriber disabled.')

        cb_group = ReentrantCallbackGroup()
        self._bool_server = ActionServer(
            self, QueryBool, '~/query_bool',
            execute_callback=self._exec_bool,
            goal_callback=lambda _: GoalResponse.ACCEPT,
            cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=cb_group,
        )
        self._int_server = ActionServer(
            self, QueryInt, '~/query_int',
            execute_callback=self._exec_int,
            goal_callback=lambda _: GoalResponse.ACCEPT,
            cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=cb_group,
        )
        self._string_server = ActionServer(
            self, QueryString, '~/query_string',
            execute_callback=self._exec_string,
            goal_callback=lambda _: GoalResponse.ACCEPT,
            cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=cb_group,
        )

    def _on_image(self, msg: Image):
        """Cache the latest image (lock-protected so action threads can read it consistently)."""
        with self._image_lock:
            self._latest_image = msg

    def _resolve_image(self, goal_image: Image) -> Image | None:
        """Prefer the goal-embedded image; fall back to the cached subscriber message; None if neither exists."""
        if not is_image_empty(goal_image):
            return goal_image
        with self._image_lock:
            return self._latest_image

    def _image_age_seconds(self, img_msg: Image) -> float | None:
        """Age in seconds against the node clock; None if the header stamp is unset (sec=0, nanosec=0)."""
        stamp = img_msg.header.stamp
        if stamp.sec == 0 and stamp.nanosec == 0:
            return None
        age_ns = (self.get_clock().now() - Time.from_msg(stamp)).nanoseconds
        return max(0.0, age_ns / 1e9)

    def _exec_bool(self, goal_handle):
        """ActionServer execute callback for QueryBool — delegates to the shared retry loop."""
        return self._execute(goal_handle, BoolParser(), QueryBool.Result, QueryBool.Feedback)

    def _exec_int(self, goal_handle):
        """ActionServer execute callback for QueryInt — delegates to the shared retry loop."""
        return self._execute(goal_handle, IntParser(), QueryInt.Result, QueryInt.Feedback)

    def _exec_string(self, goal_handle):
        """ActionServer execute callback for QueryString — delegates to the shared retry loop."""
        return self._execute(goal_handle, StringParser(), QueryString.Result, QueryString.Feedback)

    def _execute(self, goal_handle, parser, result_cls, feedback_cls):
        """Run the type-enforced VLM query loop: resolve image, prompt the VLM, parse, retry up to max_retries."""
        self.get_logger().info(f'Goal received with prompt: {goal_handle.request.prompt}')
        goal = goal_handle.request
        result = result_cls()
        result.value = parser.zero_value
        result.success = False

        img_msg = self._resolve_image(goal.image)
        if img_msg is None:
            self._publish_feedback(goal_handle, feedback_cls, 'no image available')
            self.get_logger().warn('Action goal aborted: no image available.')
            goal_handle.abort()
            return result

        # If using the live stream, make sure its recent enough
        if is_image_empty(goal.image):
            age = self._image_age_seconds(img_msg)
            if age is not None and age > self._max_image_age:
                msg = f'image is stale ({age:.2f}s > {self._max_image_age:.2f}s)'
                self._publish_feedback(goal_handle, feedback_cls, msg)
                self.get_logger().warn(f'Action goal aborted: {msg}.')
                goal_handle.abort()
                return result

        try:
            image_url = encode_image(img_msg)
        except Exception as e:
            self.get_logger().warn(f'Image encode failed: {e}')
            self._publish_feedback(goal_handle, feedback_cls, f'image encode failed: {e}')
            goal_handle.abort()
            return result

        system_msg = {
            'role': 'system',
            'content': f'{self._system_prompt}\n\n{parser.format_instruction}',
        }
        user_msg = {
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': image_url}},
                {'type': 'text', 'text': goal.prompt},
            ],
        }
        messages = [system_msg, user_msg]

        last_raw = ''
        for attempt in range(1, self._max_retries + 1):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                return result

            self._publish_feedback(
                goal_handle, feedback_cls,
                f'attempt {attempt}/{self._max_retries}',
            )

            try:
                raw = self._client.chat(messages, timeout=self._request_timeout)
            except Exception as e:
                self.get_logger().warn(f'VLM request failed on attempt {attempt}: {e}')
                self._publish_feedback(
                    goal_handle, feedback_cls,
                    f'attempt {attempt}/{self._max_retries}: request failed: {e}',
                )
                goal_handle.abort()
                return result

            last_raw = raw
            self.get_logger().debug(f'VLM raw response (attempt {attempt}): {raw!r}')
            ok, parsed, reason = parser.parse(raw)
            if ok:
                if parsed is not None:
                    result.value = parsed
                    result.success = True
                goal_handle.succeed()
                self.get_logger().info(f'Completed prompt: "{goal_handle.request.prompt}" with response: {result.value}')
                return result

            self._publish_feedback(
                goal_handle, feedback_cls,
                f'attempt {attempt}/{self._max_retries}: '
                f'{reason or "response did not match required format"}',
            )
            messages.append({'role': 'assistant', 'content': raw})
            messages.append({'role': 'user', 'content': parser.format_correction(raw, reason)})

        self.get_logger().warn(
            f'VLM retries exhausted ({self._max_retries}); last raw response: {last_raw!r}')
        goal_handle.abort()
        return result

    @staticmethod
    def _publish_feedback(goal_handle, feedback_cls, status: str):
        """Build and publish a feedback message with the given status string."""
        fb = feedback_cls()
        fb.status = status
        goal_handle.publish_feedback(fb)


def main(args=None):
    """Entry point: spin the VLM node on a MultiThreadedExecutor sized by the executor_threads parameter."""
    rclpy.init(args=args)
    node = VLMNode()
    num_threads = max(1, int(node.get_parameter('executor_threads').value))
    executor = MultiThreadedExecutor(num_threads=num_threads)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

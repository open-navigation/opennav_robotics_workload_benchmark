import base64

import cv2
from cv_bridge import CvBridge


_bridge = CvBridge()


def encode_image(img_msg) -> str:
    """Encode a sensor_msgs/Image as a base64 PNG data URL ready for an image_url payload."""
    cv_img = _bridge.imgmsg_to_cv2(img_msg, desired_encoding='bgr8')
    ok, buf = cv2.imencode('.png', cv_img)
    if not ok:
        raise RuntimeError('PNG encode failed')
    b64 = base64.b64encode(buf.tobytes()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def is_image_empty(img_msg) -> bool:
    """Return True iff the Image message is a default-constructed placeholder."""
    return img_msg.height == 0 or img_msg.width == 0 or len(img_msg.data) == 0

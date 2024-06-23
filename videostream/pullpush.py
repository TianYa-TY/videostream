# 拉流然后推流
import time
from typing import Type

from videostream.accelerator import Accelerator


class PullPush:
    def __init__(self, pull_url: str, push_url: str, accel: Type[Accelerator] = None, reconn: bool = False):
        self._pull_url = pull_url
        self._push_url = push_url
        self._accel = accel
        self._reconn = reconn
        pass


if __name__ == '__main__':
    from pull import Pull
    from push import Push

    pull = Pull("rtsp://admin:wisdri001@192.168.1.64/Stream/Channels/1", reconn=True)

    fps = pull.stream_info[0]["avg_frame_rate"]
    w, h, fr = pull.stream_info[0]["width"], pull.stream_info[0]["height"], int(eval(fps))
    push = Push("rtmp://192.168.244.98/live/test", w, h, fr)

    while True:
        if pull.has_frame():
            frame = pull.read()
            if frame is not None:
                push.put_frame(frame)
        time.sleep(0.01)



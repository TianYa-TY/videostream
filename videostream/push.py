import subprocess
import time
from queue import Queue
from threading import Thread
from typing import Type

import numpy as np

from videostream.accelerator import Accelerator
from videostream.logger import logger
from videostream.tools import release_process, run_async


class Push:
    def __init__(self, push_url: str,
                 w: int, h: int, fr: int, pix_fmt: str = "rgb24",
                 reconn: bool = False,
                 accel: Type[Accelerator] = None):
        """
        推流到服务器上
        :param push_url: 推送url
        :param w: 视频宽
        :param h: 视频高
        :param fr: 帧率
        :param pix_fmt: 像素格式
        :param reconn: 与视频流服务器断线重连
        """
        assert w > 0 and h > 0, "宽高必须大于0"
        assert 0 < fr < 120, "帧率必须大于0且小于120"
        assert pix_fmt in ["rgb24", "bgr24"]

        self._push_url = push_url
        self._w = w
        self._h = h
        self._fr = fr
        self._pix_fmt = pix_fmt
        self._reconn = reconn
        self._accel = accel

        self._is_pushing = False # 是否正在推流，用来向外界反馈推流状态
        self._stop = False  # 停止推流（用来关闭推流的信号量）
        self._q = Queue(maxsize=5)
        self._push_thread = Thread(target=self._run)
        self._ffmpeg_cmd: str | None = None

        self._make_ffmpeg_cmd()

        # 开启推流线程，等待推流进程连接服务器
        self._push_thread.start()
        wait_cnt = 0
        while not self._is_pushing and wait_cnt < 300:
            time.sleep(0.03)
            wait_cnt += 1

    def _make_ffmpeg_cmd(self):
        """生成ffmpeg命令"""
        encoder = "libx264" if self._accel is None else self._accel.get_encoder("h264")
        encoder = "libx264" if encoder == "h264" else encoder
        self._ffmpeg_cmd = ("ffmpeg "
                            "-loglevel warning "
                            "-y "
                            "-rw_timeout 3000000 "
                            f"-f rawvideo "
                            f"-pix_fmt {self._pix_fmt} "
                            f"-s {self._w}x{self._h} "
                            f"-r {self._fr} "
                            "-i - "
                            f"-c:v {encoder} "
                            "-an "
                            "-tune zerolatency "
                            "-preset ultrafast "
                            "-pix_fmt yuv420p "
                            "-f flv "
                            f"{self._push_url}")

    def _run(self):
        """推流子线程"""
        sleep_secs = max(0., 1 / self._fr - 0.007)
        frame = np.zeros((self._h, self._w, 3), dtype=np.uint8).tobytes()
        ffmpeg_proc: subprocess.Popen | None = None
        while True:
            if ffmpeg_proc is not None:
                release_process(ffmpeg_proc)
            ffmpeg_proc = run_async(self._ffmpeg_cmd)
            push_cnt = 0

            while not self._stop:
                if not self._q.empty():
                    frame = self._q.get()
                try:
                    ffmpeg_proc.stdin.write(frame)
                    ffmpeg_proc.stdin.flush()
                    push_cnt += 1
                    if push_cnt > 10:
                        self._is_pushing = True
                except BrokenPipeError:
                    logger.error("推流失败，可能是和服务器之间的网络连接问题")
                    self._is_pushing = False
                    break
                except Exception as e:
                    logger.exception("写数据失败", e)
                    self._is_pushing = False
                    break
                time.sleep(sleep_secs)

            if not self._reconn:
                break

        release_process(ffmpeg_proc)

    def put_frame(self, frame: np.ndarray):
        if not self._q.full():
            self._q.put(frame.tobytes())

    def is_pushing(self) -> bool:
        """是否正在推流"""
        return self._is_pushing

    def release(self):
        while self._push_thread.is_alive():
            self._reconn = False
            self._stop = True
            time.sleep(0.03)


if __name__ == '__main__':
    w, h, fr = 1920, 1080, 30
    pushes = [Push(f"rtmp://192.168.133.236/live/a{i}", w, h, fr, accel=None, reconn=True) for i in range(1)]

    value = 0
    while True:
        value = value + 1
        if value > 255:
            value = 0
        frame = np.full((h, w, 3), value, dtype=np.uint8)
        # frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        [push.put_frame(frame) for push in pushes]
        [print(f"\r {push.is_pushing()}", end="") for push in pushes]

        time.sleep(1 / fr)

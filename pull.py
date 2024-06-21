import subprocess
import time
from queue import Queue
from threading import Thread
from typing import Type

import cv2
import numpy as np

from accelerator import Accelerator, NvidiaAccel
from logger import logger
from tools import get_info, is_stream, run_async, release_process, get_out_numpy_shape


class Pull:
    def __init__(self, url: str, pix_fmt: str = "rgb24", reconn: bool = False, accel: Type[Accelerator] = None):
        """
        :param url: 视频文件或视频流的地址
        :param pix_fmt: 输出帧的格式， "rgb24" 或 "bgr24"
        :param reconn: 对于视频流，断线后重连，对于视频文件，播放结束后再重头开始播放
        :param accel: 使用哪个加速器，为None则不使用加速器
        """
        assert pix_fmt in ("rgb24", "bgr24", "yuv420p", "yuvj420p", "nv12", "gray")
        self._url = url
        self._pix_fmt = pix_fmt
        self._accel = accel
        self._reconn = reconn  # 多线程共享的变量，尽量只做原子操作，不能保证原子操作时就加把锁
        self._is_pulling = False  # 反馈给外部的ffmpeg拉流进程的运行状态，多线程共享的变量
        self._stop = False  # 由外部传给线程的停止信号，多线程共享的变量
        self._q = Queue(maxsize=5)
        self._prod_thread = Thread(target=self._run)
        self._ffmpeg_cmd: str | None = None

        try:
            self.stream_info = get_info(self._url)
            if self.stream_info is None or len(self.stream_info) == 0:
                logger.error("无法获取视频流信息")
                return
        except ValueError as e:
            logger.error(e)
            return

        if self._accel is not None:
            if not self._accel.check_ffmpeg():
                logger.warning("未安装ffmpeg或当前ffmpeg不支持nvidia GPU加速")
                self._accel = None
            elif self._accel.get_num() <= 0:
                logger.warning("没有可用的nvidia显卡或没有正确安装nvidia驱动")
                self._accel = None

        self._make_ffmpeg_cmd()

        # 开启读帧线程，等待线程中打开拉流进程
        self._prod_thread.start()
        cnt = 0
        while not self._is_pulling and cnt < 300:
            time.sleep(0.03)
            cnt += 1

        if cnt >= 298:
            self.release()
            logger.error("无法打开视频流")

    def _make_ffmpeg_cmd(self):
        """构造ffmpeg命令"""
        accel_opt = f"-hwaccel {self._accel.get_accel_name()}" if self._accel is not None else ""
        rtsp_opt = f"-rtsp_transport tcp" if self._url.startswith("rtsp://") else ""
        file_stream_opt = f"-re" if not is_stream(self._url) else "-flags low_delay"

        self._ffmpeg_cmd = (f"ffmpeg -loglevel warning "
                            f"{rtsp_opt} {accel_opt} {file_stream_opt} "
                            f"-i '{self._url}' "
                            f"-pix_fmt {self._pix_fmt} -f rawvideo "
                            f"pipe: ")

    def _run(self):
        # 运行在子线程中
        ffmpeg_proc: subprocess.Popen | None = None
        out_np_shape = (0, 0, 0)
        while True:
            # 检查流，开启拉流的ffmpeg进程
            try:
                self.stream_info = get_info(self._url)
                if len(self.stream_info) == 0:
                    self._is_pulling = False
                    logger.error("文件或流中没有视频流")
                else:
                    out_np_shape = get_out_numpy_shape(
                        (self.stream_info[0]["width"], self.stream_info[0]["height"]),
                        self._pix_fmt)
                    if ffmpeg_proc is not None:
                        release_process(ffmpeg_proc)
                    ffmpeg_proc = run_async(self._ffmpeg_cmd)
                    self._is_pulling = True
            except ValueError as e:
                logger.error(e)
                self._is_pulling = False
            except Exception as e:
                logger.exception("", e)
                self._is_pulling = False

            # 从ffmpeg进程读帧放入队列中
            while not self._stop: # 此信号是外部传进来的停止信号
                in_bytes = ffmpeg_proc.stdout.read(np.prod(out_np_shape))
                # 读数据错误，结束整个拉流程序
                if not in_bytes:
                    self._q.put(None)
                    self._is_pulling = False  # 告诉外界ffmpeg拉流进程死了
                    break

                img = np.frombuffer(in_bytes, np.uint8).reshape(out_np_shape)
                if self._q.full():
                    self._q.get()  # 丢弃多余的帧
                self._q.put(img)

            if not self._reconn:
                break

        release_process(ffmpeg_proc)

    def read(self, block: bool = True, timeout: float | None = None) -> np.ndarray:
        """读到None表示拉流已经关闭，或者出现错误"""
        return self._q.get(block, timeout)

    def is_opened(self) -> bool:
        """判断拉流是否打开，如果reconn设为True，那么再重连的过程中，拉流状态会是关闭的"""
        return self._is_pulling

    def has_frame(self) -> bool:
        return not self._q.empty()

    def release(self):
        """设置_is_open为false, 拉流线程重会关闭ffmpeg进程"""
        while self._prod_thread.is_alive():
            self._reconn = False
            self._stop = True
            time.sleep(0.03)


if __name__ == '__main__':
    url1 = "D:/Program Files/JetBrains/PyCharmProjects/ai-platform-manage/tests/media/output1.mp4"
    url2 = "rtsp://admin:wisdri001@192.168.1.64/Stream/Channels/1"
    url3 = "Integrated Camera"

    pulls = [Pull(url2, pix_fmt="bgr24", accel=None) for _ in range(2)]

    while True:
        frames = [pull.read(block=True) for pull in pulls]
        zip_frames = [cv2.resize(frame, (1080//len(frames), 840)) for frame in frames if frame is not None]
        cv2.imshow("frame", np.concatenate(zip_frames, axis=1))
        # cv2.imshow("frame", frames[0])
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    [pull.release() for pull in pulls]
    cv2.destroyAllWindows()

    # pull = Pull(url1, pix_fmt="bgr24", accel=None, reconn=True)
    # print(pull.stream_info)
    #
    # while pull.is_opened():
    #     frame = pull.read(block=True)
    #     if frame is not None:
    #         cv2.imshow("frame", frame)
    #
    #     if cv2.waitKey(1) & 0xFF == ord('q'):
    #         break
    # else:
    #     logger.error("拉流结束")
    #
    # pull.release()
    # cv2.destroyAllWindows()

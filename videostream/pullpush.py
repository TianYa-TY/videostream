import subprocess
import time
from threading import Thread
from typing import Type, Union

from videostream.accelerator import Accelerator, NoAccel, NvidiaAccel
from videostream.logger import logger
from videostream.tools import run_async, release_process, is_stream


class PullPush:
    def __init__(self, pull_url: str, push_url: str, reconn: bool = False, accel: Type[Accelerator] = NoAccel):
        """
        :param pull_url: 拉取视频的地址
        :param push_url: 推送视频的地址
        :param reconn: 断线重连
        :param accel: 使用的加速器，默认不使用加速器(NoAccel)
        """
        self._pull_url = pull_url
        self._push_url = push_url
        self._reconn = reconn
        self._accel = accel
        self._stop = False  # 外部输入的停止信号
        self._working = False  # ffmpeg 进程是否在运行
        self._work_thread = Thread(target=self._run)
        self._ffmpeg_cmd: Union[str, None] = None

        # 检查加速器是否可用
        if not self._accel.check_ffmpeg():
            logger.warning("未安装ffmpeg或当前ffmpeg不支持nvidia GPU加速")
            self._accel = NoAccel
        elif self._accel.get_num() <= 0:
            logger.warning("没有可用的nvidia显卡或没有正确安装nvidia驱动")
            self._accel = NoAccel

        self._make_ffmpeg_cmd()
        self._work_thread.start()
        wait_cnt = 0
        while not self._working and wait_cnt < 300:
            time.sleep(0.03)
            wait_cnt += 1

    def _make_ffmpeg_cmd(self):
        accel_opt = self._accel.get_accel_opt()
        rtsp_opt = "-rtsp_transport tcp -flags low_delay" if self._pull_url.startswith("rtsp://") else ""
        file_stream_opt = f"-re" if not is_stream(self._pull_url) else "-flags low_delay"
        encoder = self._accel.get_encoder("h264")
        encoder_param = self._accel.get_encoder_param()

        self._ffmpeg_cmd = ("ffmpeg "
                            "-loglevel warning "
                            f"{accel_opt} {rtsp_opt} {file_stream_opt} "
                            f"-i {self._pull_url} "
                            f"-c:v {encoder} {encoder_param} "
                            "-pix_fmt yuv420p -f flv "
                            f"{self._push_url}")

    def _run(self):
        # 用来维护推拉进程的线程，包括断线重连的功能
        ffmpeg_proc: Union[subprocess.Popen, None] = None
        while True:
            if ffmpeg_proc is not None:
                release_process(ffmpeg_proc)
            self._ffmpeg_process = run_async(self._ffmpeg_cmd)

            check_cnt = 0
            while self._ffmpeg_process.poll() is None:
                time.sleep(2)
                check_cnt += 1
                if check_cnt == 2:
                    self._working = True

                if self._stop:
                    break
            else:
                logger.warning("ffmpeg拉推流失败")
            self._working = False

            if not self._reconn:
                break

        release_process(ffmpeg_proc)

    def release(self):
        while self._work_thread.is_alive():
            self._reconn = False
            self._stop = True
            time.sleep(0.03)

    def is_working(self) -> bool:
        return self._working


if __name__ == '__main__':
    # ffmpeg_cmd = ("ffmpeg "
    #               "-rtsp_transport tcp "
    #               "-flags low_delay "
    #               "-i rtsp://admin:wisdri001@192.168.1.64/Stream/Channels/1 "
    #               "-c:v libx264 -tune zerolatency -preset ultrafast "
    #               "-pix_fmt yuv420p -f flv "
    #               "rtmp://127.0.0.1/live/stream2")
    #
    # proc = run_async(ffmpeg_cmd)
    #
    # proc.wait()
    #
    # print(proc.stdout.read().decode("utf-8"))

    pp = PullPush("rtsp://admin:wisdri001@192.168.1.64/Stream/Channels/1",
                  "rtmp://127.0.0.1/live/stream2", accel=NvidiaAccel)

    print(pp._ffmpeg_cmd)

    while pp.is_working():
        time.sleep(0.03)

    """
    ffmpeg -loglevel warning  -rtsp_transport tcp -flags low_delay -flags low_delay -i rtsp://admin:wisdri001@192.168.1.64/Stream/Channels/1 -c:v libx264 -tune zerolatency -preset ultrafast -pix_fmt yuv420p -f flv rtmp://127.0.0.1/live/stream2
    ffmpeg -loglevel warning -hwaccel cuda -rtsp_transport tcp -flags low_delay -flags low_delay -i rtsp://admin:wisdri001@192.168.1.64/Stream/Channels/1 -c:v h264_nvenc  -pix_fmt yuv420p -f flv rtmp://127.0.0.1/live/stream2
    """
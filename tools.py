import shlex
from subprocess import check_output, STDOUT, CalledProcessError, Popen, TimeoutExpired, DEVNULL, PIPE
import json
from typing import Sequence
import os
import signal


stream_protocols = ["rtmp", "rtsp", "http", "https", "rtmps", "hls", "dash", "m3u8"]
video_format = ["mp4", "mkv", "flv", "avi", "mov"]


def is_stream(url: str) -> bool:
    """
    根据URL前后缀判断url是视频流还是视频文件，不一定可靠
    :param url: 视频地址
    :return: False-视频文件， True-视频流
    """
    url = url.lower()
    if any(url.endswith(i) for i in video_format):
        return False
    elif any(url.startswith(i) for i in stream_protocols):
        return True
    else:
        return False


def check_url(url: str) -> bool:
    """
    判断输入视频的url是否可用
    :param url: 视频地址，视频文件或者RTSP流等
    :return: True-可用，False-不可用
    """
    try:
        check_output(shlex.split(f"ffprobe -v error -timeout 2000000 -i '{url}'"), shell=False, stderr=STDOUT)
        return True
    except CalledProcessError:
        return False


def get_out_numpy_shape(size_wh: Sequence, pix_fmt: str) -> tuple:
    """获取一帧数据的尺寸，和像素格式有关"""
    width, height = size_wh
    assert (not pix_fmt == "yuv420p") or (
            height % 2 == 0 and width % 2 == 0
    ), "yuv420p must be even"
    out_numpy_shape = {
        "rgb24": (height, width, 3),
        "bgr24": (height, width, 3),
        "yuv420p": (int(height * 1.5), width),
        "yuvj420p": (int(height * 1.5), width),
        "nv12": (int(height * 1.5), width),
        "gray": (height, width, 1)
    }[pix_fmt]
    return out_numpy_shape


def get_info(url: str, audio=False) -> list[dict]:
    """
    获取视频文件或RTSP流的信息
    视频URL有问题时回抛出异常信息
    :param url: 视频地址
    :param audio: 是否获取音频流信息, 默认不获取
    :return: 流信息列表
    """
    select_streams = "" if audio else "-select_streams v"
    rtsp_flag = "-rtsp_transport tcp" if url.startswith("rtsp://") else ""
    cmd = f"ffprobe -v error -timeout 2000000 {rtsp_flag} {select_streams} -print_format json -show_streams -i '{url}'"
    try:
        output = check_output(shlex.split(cmd), shell=False, stderr=STDOUT).decode("utf-8")

        # 如果数据包有问题，前几行会输出错误信息，所以需要去掉这些错误信息
        sp, ep = -1, len(output)
        for i, c in enumerate(output):
            if sp == -1 and c == '{':
                sp = i
            if c == '}':
                ep = i + 1

        output = json.loads(output[sp:ep])
        return output['streams']
    except CalledProcessError as e:
        # 可能的错误：
        # 1、ffprobe命令不可用
        # 2、视频文件不存在
        # 3、文件格式错误，不是视频文件
        # 4、rtsp地址错误
        raise ValueError(e.output.decode('utf-8'))


def run_async(args):
    quiet = True
    stderr_stream = DEVNULL if quiet else None
    bufsize = -1
    if isinstance(args, str):
        args = shlex.split(args)
    return Popen(
        args,
        stdin=PIPE,
        stdout=PIPE,
        stderr=stderr_stream,
        shell=False,
        bufsize=bufsize,
    )


def release_process(proc: Popen):
    if hasattr(proc, "stdin") and proc.stdin is not None:
        proc.stdin.close()
    if hasattr(proc, "stdout") and proc.stdout is not None:
        proc.stdout.close()
    if hasattr(proc, "terminate"):
        proc.terminate()
    if hasattr(proc, "wait"):
        try:
            # 等待5秒，如果terminate没有正常结束进程，则强制杀死进程
            proc.wait(timeout=5)
        except TimeoutExpired:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            elif hasattr(os, "kill"):
                os.kill(proc.pid, signal.SIGKILL)
            else:
                proc.kill()


if __name__ == '__main__':
    print(check_url("rtsp://admin:wisdri001@192.168.1.64/Stream/Channels/1"))


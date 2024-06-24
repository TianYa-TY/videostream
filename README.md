### 简介
本项目是基于ffmpeg6.1.1使用的包，用于拉取视频流，获取视频帧，进行一些处理后再推送到视频服务器上。
### 使用条件
系统环境中需要预先安装ffmpeg工具（命令与6.1.1兼容的版本即可）
### 安装方式
```bash
pip install git+https://github.com/TianYa-TY/videostream.git
```
### 使用示例
#### 基本用法
```python
from videostream import Pull, Push
import time

# 创建拉取对象；可以是一个视频流，也可以是一个视频文件。
pull = Pull("rtsp://192.168.1.64/Stream/Channels/1")

fps = pull.stream_info[0]["avg_frame_rate"]
w, h, fr = pull.stream_info[0]["width"], pull.stream_info[0]["height"], int(eval(fps))
push = Push("rtmp://127.0.0.1/live/test", w, h, fr)

while pull.is_opened() and push.is_pushing():
    # todo 捕获一个外部输入的退出信号，用来退出循环
    
    if pull.has_frame():
        frame = pull.get_frame()
        # todo 这里增加frame处理代码
        push.put_frame(frame)
    time.sleep(0.001)

pull.release()
push.release()
```
#### 增强用法
```python
from videostream import Pull, Push, accelerator
import time

# accel参数指定使用Nvidia GPU加速解码
# reconn 对于视频流，设置拉流断线后是否自动重连；对于视频文件，设置视频结束后是否重新播放
pull = Pull("rtsp://192.168.1.64/Stream/Channels/1", accel=accelerator.NvidiaAccel, reconn=True)

fps = pull.stream_info[0]["avg_frame_rate"]
w, h, fr = pull.stream_info[0]["width"], pull.stream_info[0]["height"], int(eval(fps))

# accel参数指定使用Nvidia GPU加速解码。
# reconn 指定与视频服务器断线后是否自动重连
push = Push("rtmp://127.0.0.1/live/test", w, h, fr, accel=accelerator.NvidiaAccel, reconn=True)

while True:
    # todo 捕获一个外部输入的退出信号，用来退出死循环
    
    # 如果断线, pull.is_opened() 或 push.is_pushing() 将返回False
    if not pull.is_opened() or not push.is_pushing():
        continue
    
    if pull.has_frame():
        frame = pull.get_frame()
        # todo 这里增加frame处理代码
        push.put_frame(frame)
    time.sleep(0.001)

pull.release()
push.release()
```
关于加速器的说明：  
<ol>
<li>当设置加速器为NvidiaAccel时，需要安装的ffmpeg支持cuda硬件加速，且机器带有nvidia显卡及其驱动；否则仍会使用CPU编解码。</li>
<li>目前仅支持Nvidia显卡加速，后续可能会增加AMD、Intel等显卡的支持。</li>
<li>ffmpeg 文档中关于-hwaccel选项有一段说明：多数加速方法是用于播放的，在现代CPU上，可能不会比CPU软解更快。此外系统内存和GPU内存之间的数据传输会进一步导致性能损失。因此，此选项主要用于测试。</li>
</ol>









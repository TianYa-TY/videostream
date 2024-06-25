# 拉流然后推流
import time


if __name__ == '__main__':
    from videostream import Pull
    from videostream import Push
    from videostream import accelerator

    pull = Pull("rtsp://192.168.1.64/Stream/Channels/1", reconn=True, accel=accelerator.NvidiaAccel)

    fps = pull.stream_info[0]["avg_frame_rate"]
    w, h, fr = pull.stream_info[0]["width"], pull.stream_info[0]["height"], int(eval(fps))
    print(w, h, fr)
    push = Push("rtmp://127.0.0.1/live/test", w, h, fr, accel=accelerator.NvidiaAccel)

    print(pull._ffmpeg_cmd)
    print(push._ffmpeg_cmd)


    try:
        while True:
            if pull.has_frame():
                frame = pull.get_frame()
                push.put_frame(frame)

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("exit")
    except Exception as e:
        print(e)
    finally:
        pull.release()
        push.release()


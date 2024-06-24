import re
import shlex
from subprocess import check_output
import cv2


if __name__ == "__main__":
    url1 = "D:/Program Files/tests/media/output1.mp4"
    url2 = "rtsp://192.168.1.64/Stream/Channels/1"
    cap = cv2.VideoCapture(url2)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("frame", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

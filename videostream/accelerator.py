import re
from abc import ABC, abstractmethod
from subprocess import check_output, DEVNULL, CalledProcessError
from typing import Union


class Accelerator(ABC):
    _decoder_map: dict[str, str] = dict()
    _encoder_map: dict[str, str] = dict()

    @staticmethod
    @abstractmethod
    def get_accel_opt():
        """获取加速器名称"""
        pass

    @classmethod
    @abstractmethod
    def check_ffmpeg(cls) -> bool:
        """检查当前ffmpeg是否支持此加速器"""
        pass

    @staticmethod
    def get_encoder_param() -> str:
        """获取加速器对应的编码器的参数"""
        pass

    @classmethod
    @abstractmethod
    def get_num(cls) -> int:
        """获取加速器的个数"""
        pass

    @classmethod
    def is_ok(cls) -> bool:
        """判断是否可以使用Nvidia加速器"""
        return cls.check_ffmpeg() and cls.get_num() > 0

    @classmethod
    def get_decoder(cls, codec: str) -> str:
        """
        先检查是否支持此加速器，
        如果支持，返回加速器对应的解码器，
        如不支持，返回原解码器
        """
        if not cls.is_ok():
            return codec

        if codec in cls._decoder_map:
            return cls._decoder_map[codec]
        else:
            return codec

    @classmethod
    def get_encoder(cls, codec: str) -> str:
        """
        先检查是否支持此加速器，
        如果支持，返回加速器对应的编码器，
        如不支持，返回原编码器
        """
        if not cls.is_ok():
            return codec

        if codec in cls._encoder_map:
            return cls._encoder_map[codec]
        else:
            return codec


class NoAccel(Accelerator):
    _encoder_map: dict[str, str] = {"h264": "libx264", "hevc": "libx265", "vp9": "libvpx-vp9", "av1": "libaom-av1"}
    _decoder_map: dict[str, str] = {"h264": "h264", "hevc": "hevc", "vp9": "vp9", "av1": "av1"}

    @staticmethod
    def get_accel_opt():
        return ""

    @classmethod
    def check_ffmpeg(cls) -> bool:
        return True

    @staticmethod
    def get_encoder_param() -> str:
        """获取编码器参数"""
        return "-tune zerolatency -preset ultrafast"

    @classmethod
    def get_num(cls) -> int:
        return 1


class NvidiaAccel(Accelerator):
    _ffmpeg_support: Union[bool, None] = None
    _nvidia_num: Union[int, None] = None

    _encoder_map: dict[str, str] = dict()
    _decoder_map: dict[str, str] = dict()

    _encoder_pattern = re.compile(r"V.{5} (.{2,8}_nvenc) ", re.MULTILINE)
    _decoder_pattern = re.compile(r"V.{5} (.{2,8}_cuvid) ", re.MULTILINE)

    @staticmethod
    def get_accel_opt():
        return "-hwaccel cuda"

    @staticmethod
    def get_encoder_param() -> str:
        """获取编码器参数"""
        return "-preset p1"

    @classmethod
    def check_ffmpeg(cls) -> bool:
        """检查当前ffmpeg是否支持此加速器"""
        if cls._ffmpeg_support is None:
            try:
                output = check_output(["ffmpeg", "-encoders"], stderr=DEVNULL).decode("utf-8")
                encoders = cls._encoder_pattern.findall(output)
                if len(encoders) == 0:
                    cls._ffmpeg_support = False
                    return cls._ffmpeg_support

                cls._encoder_map = {it.split("_")[0]: it for it in encoders}

                output = check_output(["ffmpeg", "-decoders"], stderr=DEVNULL).decode("utf-8")
                decoders = cls._decoder_pattern.findall(output)
                if len(decoders) == 0:
                    cls._ffmpeg_support = False
                    return cls._ffmpeg_support

                cls._decoder_map = {it.split("_")[0]: it for it in decoders}

            except CalledProcessError:
                cls._ffmpeg_support = False
                return cls._ffmpeg_support

            cls._ffmpeg_support = True

        return cls._ffmpeg_support

    @classmethod
    def get_num(cls) -> int:
        """获取加速器的个数"""
        if cls._nvidia_num is None:
            try:
                output = check_output(["nvidia-smi", "-L"], shell=False, stderr=DEVNULL).decode("utf-8")
                cls._nvidia_num = len([line for line in output.splitlines() if line.startswith("GPU ")])
            except CalledProcessError:
                cls._nvidia_num = 0
                return cls._nvidia_num

        return cls._nvidia_num


if __name__ == '__main__':
    print(NvidiaAccel.get_num())

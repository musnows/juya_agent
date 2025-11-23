# -*- coding: utf-8 -*-

import os
import sys
import json
from typing import List

# 添加腾讯云语音SDK路径
current_dir = os.path.dirname(os.path.abspath(__file__))
tx_sdk_path = os.path.join(current_dir, 'tx-speech-sdk')
if tx_sdk_path not in sys.path:
    sys.path.insert(0, tx_sdk_path)

# 标志位，表示腾讯云语音SDK是否可用
SDK_AVAILABLE = True

try:
    from common import credential
    from asr import flash_recognizer
except ImportError as e:
    print(f"导入腾讯云语音SDK失败: {e}")
    print("请确保tx-speech-sdk子模块已正确初始化")
    print("语音转写功能将不可用，但不影响其他功能")
    SDK_AVAILABLE = False


class TXSpeechRecognizer:
    """腾讯云语音识别工具类"""

    def __init__(self, appid: str, secret_id: str, secret_key: str, engine_type: str = "16k_zh"):
        """
        初始化语音识别器

        Args:
            appid: 腾讯云APPID
            secret_id: 腾讯云SECRET_ID
            secret_key: 腾讯云SECRET_KEY
            engine_type: 引擎类型，默认为16k_zh
        """
        if not SDK_AVAILABLE:
            raise RuntimeError("腾讯云语音SDK不可用，请检查SDK是否正确安装")

        if not all([appid, secret_id, secret_key]):
            raise ValueError("APPID、SECRET_ID和SECRET_KEY不能为空")

        self.appid = appid
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.engine_type = engine_type

        # 初始化凭证和识别器
        self.credential_var = credential.Credential(secret_id, secret_key)
        self.recognizer = flash_recognizer.FlashRecognizer(appid, self.credential_var)

    def recognize_mp3(self, mp3_file_path: str) -> List[str]:
        """
        识别MP3文件中的语音内容

        Args:
            mp3_file_path: MP3文件路径

        Returns:
            List[str]: 识别结果文本列表，每个元素对应一个声道的识别结果

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 参数错误
            Exception: 识别过程中的其他错误
        """
        # 检查文件是否存在
        if not os.path.exists(mp3_file_path):
            raise FileNotFoundError(f"音频文件不存在: {mp3_file_path}")

        # 检查文件格式
        if not mp3_file_path.lower().endswith('.mp3'):
            raise ValueError("目前仅支持MP3格式的音频文件")

        try:
            # 创建识别请求
            req = flash_recognizer.FlashRecognitionRequest(self.engine_type)
            req.set_filter_modal(0)        # 不过滤语气词
            req.set_filter_punc(0)         # 不过滤标点符号
            req.set_filter_dirty(0)        # 不过滤脏话
            req.set_voice_format("mp3")    # 设置音频格式为mp3
            req.set_word_info(0)           # 不返回词级别信息
            req.set_convert_num_mode(1)    # 数字转换模式

            # 读取音频文件
            with open(mp3_file_path, 'rb') as f:
                audio_data = f.read()

            # 执行识别
            result_data = self.recognizer.recognize(req, audio_data)
            resp = json.loads(result_data)

            # 检查识别结果
            request_id = resp.get("request_id", "")
            code = resp.get("code", -1)

            if code != 0:
                error_msg = resp.get("message", "未知错误")
                raise Exception(f"语音识别失败，request_id: {request_id}, code: {code}, message: {error_msg}")

            # 提取识别结果文本
            text_results = []
            flash_result = resp.get("flash_result", [])

            for channel_result in flash_result:
                text = channel_result.get("text", "")
                if text.strip():  # 只添加非空文本
                    text_results.append(text.strip())

            return text_results

        except json.JSONDecodeError as e:
            raise Exception(f"解析识别结果JSON失败: {e}")
        except Exception as e:
            raise Exception(f"语音识别过程中发生错误: {e}")


def recognize_speech_from_mp3(mp3_file_path: str, appid: str = None,
                            secret_id: str = None, secret_key: str = None) -> List[str]:
    """
    便捷函数：从MP3文件识别语音内容

    Args:
        mp3_file_path: MP3文件路径
        appid: 腾讯云APPID（可选，也可通过环境变量TX_APPID设置）
        secret_id: 腾讯云SECRET_ID（可选，也可通过环境变量TX_SECRET_ID设置）
        secret_key: 腾讯云SECRET_KEY（可选，也可通过环境变量TX_SECRET_KEY设置）

    Returns:
        List[str]: 识别结果文本列表

    Raises:
        ValueError: 参数错误或凭证未提供
        RuntimeError: SDK不可用
    """
    # 首先检查SDK是否可用
    if not SDK_AVAILABLE:
        raise RuntimeError("腾讯云语音SDK不可用，请检查SDK是否正确安装")

    # 从参数或环境变量获取凭证
    appid = appid or os.getenv('TX_APPID')
    secret_id = secret_id or os.getenv('TX_SECRET_ID')
    secret_key = secret_key or os.getenv('TX_SECRET_KEY')

    if not all([appid, secret_id, secret_key]):
        raise ValueError("请提供APPID、SECRET_ID和SECRET_KEY参数，或设置相应的环境变量")

    # 创建识别器并执行识别
    recognizer = TXSpeechRecognizer(appid, secret_id, secret_key)
    return recognizer.recognize_mp3(mp3_file_path)


# 示例用法
if __name__ == "__main__":
    # 示例配置（请替换为实际的凭证）
    APPID = os.getenv('TX_APPID', '')
    SECRET_ID = os.getenv('TX_SECRET_ID', '')
    SECRET_KEY = os.getenv('TX_SECRET_KEY', '')

    # 测试文件路径
    test_mp3_path = "../output.mp3"

    try:
        if not all([APPID, SECRET_ID, SECRET_KEY]):
            print("请设置环境变量 TX_APPID、TX_SECRET_ID、TX_SECRET_KEY 或在代码中提供凭证")
            exit(1)

        # 使用便捷函数
        results = recognize_speech_from_mp3(test_mp3_path, APPID, SECRET_ID, SECRET_KEY)

        print(f"识别完成，共识别到 {len(results)} 个声道的结果:")
        for i, text in enumerate(results, 1):
            print(f"声道 {i}: {text}")

    except Exception as e:
        print(f"识别失败: {e}")
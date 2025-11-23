#!/usr/bin/env python3
"""
视频兜底处理模块
当视频简介为空时，通过下载视频、转音频、语音转文字的方式获取内容
"""

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

from .logger import get_logger
from .tx_speech_util import recognize_speech_from_mp3


class VideoFallbackProcessor:
    """视频兜底处理器"""

    def __init__(self, project_root: Path = None):
        """
        初始化兜底处理器

        Args:
            project_root: 项目根目录，如果为None则使用默认值
        """
        self.logger = get_logger("video_fallback")

        # 设置项目根目录
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent

        self.project_root = project_root
        self.data_dir = project_root / "data"
        self.video_dir = self.data_dir / "video"

        # 确保目录存在
        self.video_dir.mkdir(parents=True, exist_ok=True)

    def _is_tx_speech_configured(self) -> bool:
        """
        检查腾讯云语音SDK是否已配置

        Returns:
            bool: 是否已配置
        """
        # 检查必要的环境变量是否已设置
        appid = os.getenv('TX_APPID')
        secret_id = os.getenv('TX_SECRET_ID')
        secret_key = os.getenv('TX_SECRET_KEY')

        configured = all([appid, secret_id, secret_key])

        if not configured:
            missing_vars = []
            if not appid:
                missing_vars.append('TX_APPID')
            if not secret_id:
                missing_vars.append('TX_SECRET_ID')
            if not secret_key:
                missing_vars.append('TX_SECRET_KEY')
            self.logger.debug(f"缺少环境变量: {', '.join(missing_vars)}")

        return configured

    def should_skip_file_generation(self, video_info: Dict) -> bool:
        """
        判断是否应该跳过文件生成（简介短且无SDK配置）

        Args:
            video_info: 视频信息字典

        Returns:
            bool: 是否应该跳过文件生成
        """
        desc = video_info.get('desc', '').strip()

        # 检查简介长度
        if len(desc) < 30:
            self.logger.info(f"📏 视频简介长度为 {len(desc)} 字符，小于30字符阈值")

            # 检查腾讯云语音SDK是否已配置
            if not self._is_tx_speech_configured():
                self.logger.warning("⚠️ 腾讯云语音SDK未配置，跳过文件生成")
                self.logger.info("   请设置环境变量 TX_APPID、TX_SECRET_ID、TX_SECRET_KEY")
                return True

        return False

    def should_trigger_fallback(self, video_info: Dict) -> bool:
        """
        判断是否应该触发兜底逻辑

        Args:
            video_info: 视频信息字典

        Returns:
            bool: 是否应该触发兜底逻辑
        """
        desc = video_info.get('desc', '').strip()

        # 检查简介长度
        if len(desc) < 30:
            self.logger.info(f"📏 视频简介长度为 {len(desc)} 字符，小于30字符阈值")

            # 检查腾讯云语音SDK是否已配置
            if not self._is_tx_speech_configured():
                self.logger.warning("⚠️ 腾讯云语音SDK未配置，跳过兜底逻辑")
                self.logger.info("   请设置环境变量 TX_APPID、TX_SECRET_ID、TX_SECRET_KEY")
                return False

            self.logger.info("🔄 触发视频兜底处理逻辑")
            return True

        return False

    def download_video(self, bvid: str, date_dir: str) -> Optional[str]:
        """
        下载B站视频

        Args:
            bvid: BV号
            date_dir: 日期目录名 (YYYYMMDD)

        Returns:
            str|None: 下载的视频文件路径，失败时返回None
        """
        target_dir = self.video_dir / date_dir
        target_dir.mkdir(exist_ok=True)

        # 构建B站视频URL
        video_url = f"https://www.bilibili.com/video/{bvid}/"

        self.logger.info(f"📥 开始下载视频: {bvid}")
        self.logger.info(f"   目标目录: {target_dir}")

        try:
            # 构建you-get命令
            cmd = [
                'you-get',
                video_url,
                '-o', str(target_dir)  # 输出目录
            ]

            self.logger.info(f"🔧 执行命令: {' '.join(cmd)}")

            # 执行下载命令，设置超时为600秒
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                encoding='utf-8'
            )

            if result.returncode != 0:
                self.logger.error(f"❌ 视频下载失败:")
                self.logger.error(f"   错误输出: {result.stderr}")
                return None

            self.logger.info("✅ 视频下载命令执行完成")
            self.logger.info(f"   标准输出: {result.stdout}")

            # 查找下载的视频文件，重点查找 [01].mp4 结尾的文件
            video_files = list(target_dir.glob("*[01].mp4"))

            if not video_files:
                # 如果没找到[01].mp4，查找任意mp4文件
                video_files = list(target_dir.glob("*.mp4"))

            if not video_files:
                self.logger.error("❌ 未找到下载的视频文件")
                return None

            # 选择第一个找到的视频文件
            video_file = video_files[0]

            # 检查文件大小（大于10KB）
            file_size = video_file.stat().st_size
            if file_size <= 10 * 1024:  # 10KB
                self.logger.error(f"❌ 视频文件太小: {file_size} 字节，可能是空文件")
                return None

            self.logger.info(f"✅ 找到视频文件: {video_file}")
            self.logger.info(f"   文件大小: {file_size / 1024 / 1024:.2f} MB")

            return str(video_file)

        except subprocess.TimeoutExpired:
            self.logger.error("❌ 视频下载超时（600秒）")
            return None
        except Exception as e:
            self.logger.error(f"❌ 视频下载过程中发生错误: {e}")
            return None

    def convert_to_mp3(self, video_path: str) -> Optional[str]:
        """
        将视频文件转换为MP3音频

        Args:
            video_path: 视频文件路径

        Returns:
            str|None: 转换后的MP3文件路径，失败时返回None
        """
        video_file = Path(video_path)
        mp3_file = video_file.parent / "output.mp3"

        self.logger.info(f"🔄 开始转换视频到音频:")
        self.logger.info(f"   输入文件: {video_path}")
        self.logger.info(f"   输出文件: {mp3_file}")

        try:
            # 构建ffmpeg命令
            cmd = [
                'ffmpeg',
                '-i', video_path,           # 输入文件
                '-codec:a', 'libmp3lame',   # 音频编码器
                '-b:a', '128k',             # 比特率
                '-y',                       # 覆盖输出文件
                str(mp3_file)               # 输出文件
            ]

            self.logger.info(f"🔧 执行命令: {' '.join(cmd)}")

            # 执行转换命令，设置超时为600秒
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                encoding='utf-8'
            )

            if result.returncode != 0:
                self.logger.error(f"❌ 音频转换失败:")
                self.logger.error(f"   错误输出: {result.stderr}")
                return None

            # 检查输出文件是否存在且大小大于10KB
            if not mp3_file.exists():
                self.logger.error("❌ MP3文件未生成")
                return None

            file_size = mp3_file.stat().st_size
            if file_size <= 10 * 1024:  # 10KB
                self.logger.error(f"❌ MP3文件太小: {file_size} 字节，可能是空文件")
                return None

            self.logger.info(f"✅ 音频转换完成:")
            self.logger.info(f"   文件大小: {file_size / 1024 / 1024:.2f} MB")

            return str(mp3_file)

        except subprocess.TimeoutExpired:
            self.logger.error("❌ 音频转换超时（600秒）")
            return None
        except Exception as e:
            self.logger.error(f"❌ 音频转换过程中发生错误: {e}")
            return None

    def speech_to_text(self, mp3_path: str) -> Optional[List[str]]:
        """
        将音频文件转换为文字

        Args:
            mp3_path: MP3文件路径

        Returns:
            List[str]|None: 识别结果文本列表，失败时返回None
        """
        self.logger.info(f"🎤 开始语音转文字:")
        self.logger.info(f"   音频文件: {mp3_path}")

        try:
            # 使用腾讯云SDK进行语音识别
            results = recognize_speech_from_mp3(mp3_path)

            if not results:
                self.logger.warning("⚠️ 语音识别结果为空")
                return []

            self.logger.info(f"✅ 语音识别完成:")
            self.logger.info(f"   识别到 {len(results)} 个声道的结果")

            for i, text in enumerate(results, 1):
                self.logger.info(f"   声道 {i}: {text[:100]}...")  # 只显示前100个字符

            return results

        except RuntimeError as e:
            # 处理SDK不可用的特殊情况
            self.logger.error(f"❌ 腾讯云语音SDK不可用: {e}")
            self.logger.info("   请确保tx-speech-sdk子模块已正确初始化")
            return None
        except Exception as e:
            self.logger.error(f"❌ 语音识别失败: {e}")
            return None

    def process_video_fallback(self, bvid: str, video_info: Dict) -> Optional[List[str]]:
        """
        执行完整的视频兜底处理流程

        Args:
            bvid: BV号
            video_info: 视频信息

        Returns:
            List[str]|None: 识别的文字结果，失败时返回None
        """
        self.logger.info("🚀 开始执行视频兜底处理流程")

        # 1. 生成日期目录
        date_str = datetime.now().strftime('%Y%m%d')

        # 2. 下载视频
        video_path = self.download_video(bvid, date_str)
        if not video_path:
            self.logger.error("❌ 视频下载失败，兜底处理终止")
            return None

        # 3. 转换为音频
        mp3_path = self.convert_to_mp3(video_path)
        if not mp3_path:
            self.logger.error("❌ 音频转换失败，兜底处理终止")
            return None

        # 4. 语音转文字
        text_results = self.speech_to_text(mp3_path)
        if text_results is None:
            self.logger.error("❌ 语音识别失败，兜底处理终止")
            return None

        self.logger.info("🎉 视频兜底处理流程完成")
        return text_results
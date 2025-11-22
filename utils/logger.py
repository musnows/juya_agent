#!/usr/bin/env python3
"""
日志配置模块
提供统一的日志配置和管理功能
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class JuyaLogger:
    """橘鸦AI早报日志管理器"""

    def __init__(self, name: str = "juya", log_level: str = "INFO"):
        """
        初始化日志管理器

        Args:
            name: 日志器名称
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.name = name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """设置日志器"""
        # 创建日志器
        logger = logging.getLogger(self.name)
        logger.setLevel(self.log_level)

        # 避免重复添加处理器
        if logger.handlers:
            return logger

        # 创建日志目录
        project_root = Path(__file__).resolve().parent.parent
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        # 生成日志文件名（按日期）
        today_str = datetime.now().strftime('%Y-%m-%d')
        log_file = log_dir / f"{self.name}_{today_str}.log"

        # 创建格式器
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)

        # 添加处理器到日志器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)

    def info(self, message: str):
        """记录一般信息"""
        self.logger.info(message)

    def warning(self, message: str):
        """记录警告信息"""
        self.logger.warning(message)

    def error(self, message: str):
        """记录错误信息"""
        self.logger.error(message)

    def critical(self, message: str):
        """记录严重错误信息"""
        self.logger.critical(message)


# 创建默认的日志器实例
default_logger = JuyaLogger("juya")


# 为了兼容现有代码，提供简单的函数接口
def get_logger(name: str = "juya", log_level: str = "INFO") -> JuyaLogger:
    """
    获取日志器实例

    Args:
        name: 日志器名称
        log_level: 日志级别

    Returns:
        日志器实例
    """
    return JuyaLogger(name, log_level)


# 便捷的日志函数，直接使用默认日志器
def debug(message: str):
    """记录调试信息"""
    default_logger.debug(message)


def info(message: str):
    """记录一般信息"""
    default_logger.info(message)


def warning(message: str):
    """记录警告信息"""
    default_logger.warning(message)


def error(message: str):
    """记录错误信息"""
    default_logger.error(message)


def critical(message: str):
    """记录严重错误信息"""
    default_logger.critical(message)
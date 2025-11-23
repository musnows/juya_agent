#!/usr/bin/env python3
"""
Unified logging configuration for Juya Agent project
Provides centralized logging management across all modules
"""
import logging
import os
from datetime import datetime
from pathlib import Path


# Global logger instance
_logger_instance = None


def get_logger(name: str = None, log_level: str = "INFO") -> logging.Logger:
    """
    Get unified logger instance for all modules

    Args:
        name: Module name (will be prefixed with 'juya_')
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging.Logger: Unified logger instance
    """
    global _logger_instance

    if _logger_instance is None:
        _logger_instance = _setup_unified_logger(log_level)

    return _logger_instance


def _setup_unified_logger(log_level: str) -> logging.Logger:
    """Setup unified logger configuration"""
    # Create main logger
    logger = logging.getLogger('juya')
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create logs directory
    project_root = Path(__file__).resolve().parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    # Generate log filename with date
    today_str = datetime.now().strftime('%Y-%m-%d')
    log_file = log_dir / f"juya_{today_str}.log"

    # Create concise formatter (single line, no emojis)
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Convenience functions for direct access
def debug(message: str):
    """Log debug message"""
    get_logger().debug(message)


def info(message: str):
    """Log info message"""
    get_logger().info(message)


def warning(message: str):
    """Log warning message"""
    get_logger().warning(message)


def error(message: str):
    """Log error message"""
    get_logger().error(message)


def critical(message: str):
    """Log critical message"""
    get_logger().critical(message)
"""
日志配置模块
使用 loguru 实现日志记录，支持日志轮转和自动清理
"""
import os
import sys
from pathlib import Path
from loguru import logger
from datetime import datetime


def setup_logger():
    """
    配置 loguru 日志
    
    功能：
    1. 创建 logs 目录
    2. 配置日志文件轮转（每天一个文件）
    3. 自动清理 5 天前的日志
    4. 同时输出到控制台和文件
    """
    # 1. 确定日志目录路径
    # 项目根目录：code_diff_project
    project_root = Path(__file__).resolve().parent.parent.parent
    logs_dir = project_root / "logs"
    
    # 2. 创建 logs 目录（如果不存在）
    logs_dir.mkdir(exist_ok=True)
    
    # 3. 移除默认的 logger 配置
    logger.remove()
    
    # 4. 添加控制台输出（保持原有的控制台日志）
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # 5. 添加文件输出
    log_file_path = logs_dir / "analysis_{time:YYYY-MM-DD}.log"
    
    logger.add(
        str(log_file_path),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",  # 文件记录更详细的日志
        rotation="00:00",  # 每天午夜轮转
        retention="5 days",  # 保留 5 天
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
        enqueue=True,  # 异步写入，提高性能
    )
    
    logger.info(f"日志系统初始化完成，日志目录: {logs_dir}")
    logger.info(f"日志保留策略: 保留最近 5 天的日志文件")
    
    return logger


# 在模块导入时自动初始化
setup_logger()

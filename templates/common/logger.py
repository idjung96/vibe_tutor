"""공통 로거. 1단계에서 동작을 확인하고, 이후 수정하지 않는다.

사용법:
    from common.logger import get_logger
    logger = get_logger(__name__)
    logger.info("회원 저장 완료 | user_id=%s", user_id)
"""
import logging
import os
import sys

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def get_logger(module_name: str) -> logging.Logger:
    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger
    os.makedirs(LOG_DIR, exist_ok=True)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    stream_handler = logging.StreamHandler(sys.stdout)
    for handler in (file_handler, stream_handler):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger

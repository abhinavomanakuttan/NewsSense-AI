import logging
from pathlib import Path
import sys

from loguru import logger

from .config import settings


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    logger.remove()
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Ensure logs folder exists
    Path("logs").mkdir(parents=True, exist_ok=True)

    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.debug else "INFO",
        colorize=True,
    )

    logger.add(
        "logs/smartfeed.log",
        rotation="100 MB",
        retention="30 days",
        format=log_format,
        level="INFO",
        enqueue=True,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

    # Suppress verbose noisy logs unless debugging
    for logger_name in ("uvicorn.access", "sqlalchemy.engine", "httpcore", "httpx"):
        logging.getLogger(logger_name).handlers = [InterceptHandler()]
        if not settings.debug:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

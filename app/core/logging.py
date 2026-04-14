import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        level = record.levelname
        logger.opt(exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
    )

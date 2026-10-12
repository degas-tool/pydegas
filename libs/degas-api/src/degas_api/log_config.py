import logging
import sys
from types import FrameType

from loguru import logger

_handler_ids: list[int] = []


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _configure_stdlib_logging(level: str) -> None:
    logging.basicConfig(handlers=[_InterceptHandler()], level=level, force=True)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logging.getLogger(name).handlers = [
            _InterceptHandler(),
        ]
        logging.getLogger(name).propagate = False


def configure_logging(
    *,
    level: str,
) -> None:
    logger.remove()

    logger.configure(
        extra={
            "request_id": "-",
            "method": "-",
            "status": "system",
        }
    )
    configured_level = level.upper()
    logger.debug(
        "configuring logging level={level}",
        level=configured_level,
    )

    def terminal_format(record):
        return (
            "<dim><green>{time:YYYY-MM-DD}</green> <green>{time:HH:mm:ss.SSS}</green></dim> "
            "<b>|</b> <level><b>{level: <8}</b></level> "
            "<b>|</b> <cyan>{extra[request_id]}</cyan> "
            "<yellow>{extra[method]}</yellow> "
            "<red>{extra[status]}</red> "
            "<b>|</b> <level>{message}</level>\n"
            "{exception}"
        )

    enable_debug = configured_level == "DEBUG"
    handler_id = logger.add(
        sys.stderr,
        level=configured_level,
        format=terminal_format,
        backtrace=enable_debug,
        diagnose=enable_debug,
        catch=True,
        enqueue=True,
    )
    _handler_ids.append(handler_id)

    _configure_stdlib_logging(configured_level)

    logger.info("logging configured")


def cleanup_logging() -> None:
    global _handler_ids
    for handler_id in _handler_ids:
        try:
            logger.remove(handler_id)
        except ValueError:
            pass
    _handler_ids.clear()
    logger.complete()

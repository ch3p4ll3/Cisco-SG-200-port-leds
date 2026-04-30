import logging
from logging import config
from pathlib import Path


def configure_logger(base_path: Path):
    base_path = base_path.parent / "data/logs/"
    if not base_path.exists():
        base_path.mkdir(parents=True, exist_ok=True)

    # Logging configuration dictionary
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": base_path / "switch-leds.log",
                "when": "midnight",
                "interval": 1,
                "backupCount": 7,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "watchfiles.main": {
                "level": "WARNING",  # Suppress DEBUG logs for watchfiles.main
                "handlers": [
                    "console"
                ],  # Optionally include this for higher-level messages
                "propagate": False,
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
        },
    }

    # Apply logging configuration
    logging.config.dictConfig(logging_config)

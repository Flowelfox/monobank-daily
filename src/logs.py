import logging.config
from pathlib import Path
from warnings import filterwarnings

from telegram.warnings import PTBUserWarning


def setup_logging(project_root: Path):
    logs_folder = project_root / "logs"
    if not logs_folder.exists():
        logs_folder.mkdir()
    filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                    "datefmt": "%Y-%m-%d,%H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "level": "INFO",
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                },
                "console_warnings": {
                    "level": "ERROR",
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                },
                "deb_file": {
                    "level": "DEBUG",
                    "formatter": "default",
                    "class": "logging.handlers.RotatingFileHandler",
                    "maxBytes": 10485760,
                    "backupCount": 5,
                    "encoding": "utf8",
                    "filename": str(logs_folder / "app.log"),
                },
                "err_file": {
                    "level": "ERROR",
                    "formatter": "default",
                    "class": "logging.handlers.RotatingFileHandler",
                    "maxBytes": 10485760,
                    "backupCount": 5,
                    "encoding": "utf8",
                    "filename": str(logs_folder / "errors.log"),
                },
            },
            "loggers": {
                "": {
                    "handlers": ["console", "deb_file", "err_file"],
                    "level": "DEBUG",
                    "propagate": True,
                },
                "telegram": {
                    "handlers": ["console", "deb_file", "err_file"],
                    "level": "INFO",
                    "propagate": False,
                },
                "sqlalchemy": {
                    "handlers": ["console"],
                    "level": "WARNING",
                    "propagate": False,
                },
                "httpx": {
                    "handlers": ["console"],
                    "level": "WARNING",
                    "propagate": False,
                },
            },
        }
    )

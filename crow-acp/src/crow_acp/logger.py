import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from crow_acp.constants import LOG_DIR, LOG_PATH

# 1. Define paths safely

# 2. Ensure the directory exists (prevents FileNotFoundError)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger(name="crow_logger", log_file=LOG_PATH, max_mb=5, max_files=3):
    """
    Sets up a rotating file logger.

    :param name: Name of the logger.
    :param log_file: Path object or string to the log file.
    :param max_mb: Maximum size in Megabytes before rotating.
    :param max_files: Maximum number of backup files to keep.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Set your base logging level here

    # 3. Prevent duplicate log entries if this function is called multiple times
    if not logger.handlers:
        # 4. Set up the RotatingFileHandler
        # maxBytes triggers the rotation, backupCount limits the total files
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_mb * 1024 * 1024, backupCount=max_files
        )

        # 5. Define a readable log format
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        # 6. Attach the handler
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()

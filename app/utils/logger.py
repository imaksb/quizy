import logging
import os
import sys

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
handlers: list[logging.Handler] = [stream_handler]

if log_file := os.getenv("LOG_FILE"):
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)

logger.handlers = handlers

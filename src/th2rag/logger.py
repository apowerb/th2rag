import logging
import sys

# create a logger instance
logger = logging.getLogger()

# create a formatter
formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s")

# create handlers
stream_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler("app.log")

# set formatter for the handlers
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# add handlers to the logger
logger.handlers = [stream_handler, file_handler]

logger.setLevel(logging.INFO)

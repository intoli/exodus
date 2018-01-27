import logging


__version__ = '0.0.1'

root_logger = logging.getLogger(__name__)
if root_logger.handlers:
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

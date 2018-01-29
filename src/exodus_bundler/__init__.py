import logging


__version__ = '0.0.1'

root_logger = logging.getLogger(__name__)
root_logger.handlers = [logging.NullHandler()]

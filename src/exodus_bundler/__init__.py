import logging


__version__ = '0.0.3'

root_logger = logging.getLogger(__name__)
root_logger.handlers = [logging.NullHandler()]

import logging


__version__ = '1.1.4'

root_logger = logging.getLogger(__name__)
root_logger.handlers = [logging.NullHandler()]

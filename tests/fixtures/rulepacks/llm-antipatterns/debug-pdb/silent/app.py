import logging

logger = logging.getLogger(__name__)


def f():
    logger.debug("checkpoint")
    return 1

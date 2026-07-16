import logging

logger = logging.getLogger(__name__)


def load(path):
    try:
        return open(path).read()
    except FileNotFoundError as e:
        logger.warning("missing file: %s", e)
        return None

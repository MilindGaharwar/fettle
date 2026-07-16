import logging

logger = logging.getLogger(__name__)


def run(job):
    try:
        job.execute()
    except Exception as e:
        logger.error("job failed: %s", e, exc_info=True)

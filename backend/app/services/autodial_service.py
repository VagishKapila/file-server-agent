import logging

logger = logging.getLogger("autodial")

async def trigger_call(*args, **kwargs):
    logger.warning("autodial_service is disabled — use /autodial/start")
    return False
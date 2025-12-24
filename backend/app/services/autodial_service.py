# backend/app/services/autodial_service.py

import logging

logger = logging.getLogger("autodial")

async def trigger_call(*args, **kwargs):
    logger.warning(
        "⚠️ autodial_service.trigger_call() is deprecated. "
        "Calls must go through /autodial/start only."
    )
    return False
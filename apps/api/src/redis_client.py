import logging
from typing import Optional
import redis.asyncio as aioredis
from src.config import settings

logger = logging.getLogger(__name__)

_redis_instance: Optional[aioredis.Redis] = None


async def init_redis() -> aioredis.Redis:
    global _redis_instance
    if _redis_instance is None:
        try:
            _redis_instance = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0
            )
            # Test ping
            await _redis_instance.ping()
            logger.info("Successfully connected to Redis at %s", settings.REDIS_URL)
        except Exception as e:
            logger.warning("Could not connect to Redis at %s: %s. Using in-memory fallback for local/testing if available.", settings.REDIS_URL, e)
            try:
                import fakeredis.aioredis
                _redis_instance = fakeredis.aioredis.FakeRedis(decode_responses=True)
                logger.info("Initialized in-memory FakeRedis instance")
            except Exception as fe:
                logger.error("Failed to initialize FakeRedis fallback: %s", fe)
                raise e
    return _redis_instance


async def close_redis() -> None:
    global _redis_instance
    if _redis_instance is not None:
        await _redis_instance.close()
        _redis_instance = None


async def get_redis() -> aioredis.Redis:
    global _redis_instance
    if _redis_instance is None:
        return await init_redis()
    return _redis_instance

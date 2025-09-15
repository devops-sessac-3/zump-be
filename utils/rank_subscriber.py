import asyncio
import logging
import redis.asyncio as aioredis
from utils.queue_notifier import broadcast_concert_ranks


logger = logging.getLogger(__name__)
CHANNEL = "queue:rank_request"


class RankSubscriber:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._task: asyncio.Task | None = None
        self._running: bool = False

    async def _loop(self):
        self._running = True
        redis = aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        logger.info("RankSubscriber subscribed to %s", CHANNEL)
        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                if message.get("type") != "message":
                    continue
                concert_se = message.get("data")
                if not concert_se:
                    continue
                try:
                    await broadcast_concert_ranks(redis, concert_se, limit=200)
                except Exception as e:
                    logger.error("broadcast_concert_ranks error: %s", e)
        finally:
            try:
                await pubsub.unsubscribe(CHANNEL)
            except Exception:
                pass
            await redis.close()
            self._running = False

    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


rank_subscriber = RankSubscriber()



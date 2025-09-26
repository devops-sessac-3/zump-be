from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from redis import asyncio as aioredis

from utils.config import config


class AsyncRedisClient:
    """논블로킹 Redis 클라이언트(Singleton).

    - 기본 KV/ZSET/HASH 연산용 `redis` 인스턴스 제공
    - Pub/Sub 수신을 위한 `pubsub` 스트림 유틸 제공
    """

    _instance: Optional["AsyncRedisClient"] = None

    def __init__(self) -> None:
        redis_cfg = config.get_config("REDIS")
        self._redis = aioredis.Redis(
            host=redis_cfg["HOST"],
            port=redis_cfg["PORT"],
            db=redis_cfg.get("DB", 0),
            password=redis_cfg.get("PASSWORD"),
            encoding="utf-8",
            decode_responses=True,
        )

    @classmethod
    def instance(cls) -> "AsyncRedisClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def redis(self) -> aioredis.Redis:
        return self._redis

    async def ping(self) -> bool:
        """PING 테스트(헬스체크에서 사용)."""
        try:
            return await self._redis.ping()
        except Exception:
            return False

    async def publish(self, channel: str, message: str) -> int:
        return await self._redis.publish(channel, message)

    async def subscribe_iter(self, channel: str) -> AsyncIterator[str]:
        """해당 채널에 대한 메시지를 비동기 이터레이터로 반환."""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for raw in pubsub.listen():
                if raw.get("type") == "message":
                    data = raw.get("data")
                    if isinstance(data, bytes):
                        yield data.decode("utf-8")
                    else:
                        yield str(data)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def close(self) -> None:
        await self._redis.close()
        try:
            await self._redis.connection_pool.disconnect()
        except Exception:
            pass


# 전역 단일 인스턴스 접근자
redis_client = AsyncRedisClient.instance()

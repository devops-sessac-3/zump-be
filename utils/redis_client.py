"""
Redis ZSet 기반 대기열 유틸리티
"""
import time
from typing import List, Tuple, Optional

from redis.asyncio import Redis


class RedisQueue:
    """공연별 대기열 관리를 위한 Redis ZSet 래퍼"""

    def __init__(self, redis: Redis, namespace: str = "queue"):
        self.redis = redis
        self.namespace = namespace

    def _zset_key(self, concert_se: str) -> str:
        return f"{self.namespace}:concert:{concert_se}"

    def _user_meta_key(self, user_id: str) -> str:
        return f"{self.namespace}:user:{user_id}:meta"

    async def add_user(self, concert_se: str, user_id: str, priority: int = 0, ts_ms: Optional[int] = None) -> None:
        """사용자를 대기열(ZSet)에 추가. 낮은 score가 더 앞선 순번.
        score = priority * 1e13 + timestamp(ms)
        우선순위(priority)가 낮을수록 먼저 입장.
        """
        now_ms = ts_ms or int(time.time() * 1000)
        score = priority * 10_000_000_000_000 + now_ms
        key = self._zset_key(concert_se)
        await self.redis.zadd(key, {user_id: score})
        await self.redis.hset(self._user_meta_key(user_id), mapping={"concert_se": concert_se, "score": score, "ts": now_ms, "priority": priority})

    async def remove_user(self, concert_se: str, user_id: str) -> None:
        key = self._zset_key(concert_se)
        await self.redis.zrem(key, user_id)
        await self.redis.delete(self._user_meta_key(user_id))

    async def get_user_meta(self, user_id: str) -> Optional[dict]:
        meta = await self.redis.hgetall(self._user_meta_key(user_id))
        return meta or None

    async def get_user_concert_se(self, user_id: str) -> Optional[str]:
        meta = await self.get_user_meta(user_id)
        if not meta:
            return None
        return meta.get("concert_se")

    async def get_rank(self, concert_se: str, user_id: str) -> Optional[int]:
        key = self._zset_key(concert_se)
        rank = await self.redis.zrank(key, user_id)
        return None if rank is None else int(rank)

    async def get_count(self, concert_se: str) -> int:
        key = self._zset_key(concert_se)
        return int(await self.redis.zcard(key))

    async def pop_n(self, concert_se: str, n: int) -> List[str]:
        """앞에서부터 n명 꺼내고 제거"""
        key = self._zset_key(concert_se)
        # ZRANGE + ZREM pipeline (Redis 7은 ZPOPMIN with count 지원, 호환성 위해 아래 방식 사용)
        ids = await self.redis.zrange(key, 0, n - 1)
        if not ids:
            return []
        pipe = self.redis.pipeline()
        for uid in ids:
            pipe.zrem(key, uid)
            pipe.delete(self._user_meta_key(uid.decode() if isinstance(uid, bytes) else uid))
        await pipe.execute()
        # bytes -> str 변환
        return [uid.decode() if isinstance(uid, bytes) else uid for uid in ids]



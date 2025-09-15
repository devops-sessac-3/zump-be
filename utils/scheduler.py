"""
대기열 스케줄러

주요 기능:
- 고정 간격으로 각 공연별 대기열에서 사용자를 입장시킴
- 입장 완료 시 SSE 알림 전송
- 순번 업데이트를 위한 Pub/Sub 이벤트 발행
"""

import asyncio
from typing import List

import redis.asyncio as aioredis

from utils.redis_client import RedisQueue
from utils.sse import sse_manager


class QueueScheduler:
    """
    고정 간격으로 각 공연별 대기열에서 사용자를 입장시키는 스케줄러
    
    Attributes:
        concert_ids: 관리할 공연 ID 목록
        batch_size_per_sec: 초당 입장시킬 사용자 수
        redis_url: Redis 연결 URL
    """

    def __init__(self, concert_ids: List[str], batch_size_per_sec: int = 100, redis_url: str = "redis://localhost:6379"):
        self.concert_ids = concert_ids  # 관리할 공연 ID 목록
        self.batch_size_per_sec = batch_size_per_sec  # 초당 입장시킬 사용자 수
        self.redis_url = redis_url  # Redis 연결 URL
        self._task: asyncio.Task | None = None  # 백그라운드 태스크
        self._running: bool = False  # 실행 상태 플래그

    async def _loop(self):
        """스케줄러 메인 루프 (1초마다 실행)"""
        self._running = True
        try:
            redis_client = aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
            queue = RedisQueue(redis_client)
            
            while self._running:
                # 각 공연별로 대기열 처리
                for cid in self.concert_ids:
                    # 상위 N명의 사용자를 대기열에서 제거 (입장 처리)
                    user_ids = await queue.pop_n(cid, self.batch_size_per_sec)
                    
                    if user_ids:
                        # 입장 완료 알림을 각 사용자에게 SSE로 전송
                        for uid in user_ids:
                            await sse_manager.send(uid, {"type": "enter", "concert_se": cid})
                        
                        # 입장 후 순번 업데이트를 위해 Pub/Sub 발행 (다른 사용자들의 순번 업데이트)
                        await redis_client.publish("queue:rank_request", cid)
                        print(f"[SCHEDULER] {len(user_ids)} users entered concert {cid}, broadcasting rank updates")
                
                # 1초 대기 후 다음 배치 처리
                await asyncio.sleep(1)
        finally:
            self._running = False

    async def start(self):
        """스케줄러 시작"""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        """스케줄러 중지"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# 전역 스케줄러 (기본: 하루 최대 5공연, 초당 10명 입장)
default_scheduler = QueueScheduler(concert_ids=["1", "2", "3", "4", "5"], batch_size_per_sec=10)



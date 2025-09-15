"""
대기열 순번 업데이트 브로드캐스트 유틸리티

주요 기능:
- Redis에서 대기열 정보를 조회하여 사용자들에게 순번 업데이트 전송
- SSE를 통한 실시간 순번/진행률 브로드캐스트
- 성능 최적화를 위한 상위 N명만 대상으로 제한
"""

import logging
import redis.asyncio as aioredis
from utils.redis_client import RedisQueue
from utils.sse import sse_manager


logger = logging.getLogger(__name__)


async def broadcast_concert_ranks(redis: aioredis.Redis, concert_se: str, limit: int | None = None) -> None:
    """
    해당 공연 대기열의 모든(또는 상위 limit) 사용자에게 현재 순번/총원을 SSE로 전송
    
    Args:
        redis: Redis 연결 객체
        concert_se: 공연 식별자
        limit: 브로드캐스트할 상위 사용자 수 제한 (None이면 전체)
    """
    queue = RedisQueue(redis)
    total = await queue.get_count(concert_se)  # 현재 총 대기자 수
    
    # 상위 limit만 계산하여 부하 완화 (성능 최적화)
    end_idx = -1 if limit is None else max(0, limit - 1)
    zkey = queue._zset_key(concert_se)
    user_ids = await redis.zrange(zkey, 0, end_idx)  # ZSet에서 상위 사용자 ID 목록 조회
    
    if not user_ids:
        return
        
    # 파이프라인을 사용하여 사용자 메타데이터 일괄 조회 (성능 최적화)
    pipe = redis.pipeline()
    for uid in user_ids:
        user_id = uid if isinstance(uid, str) else uid.decode()
        pipe.hgetall(queue._user_meta_key(user_id))
    metas = await pipe.execute()

    # 각 사용자에게 순번 업데이트 전송
    for idx, uid in enumerate(user_ids, start=1):
        user_id = uid if isinstance(uid, str) else uid.decode()
        meta = metas[idx - 1] or {}
        initial_total = int(meta.get("initial_total", total)) if isinstance(meta, dict) else total
        
        # SSE 페이로드 구성
        payload = {
            "type": "rank",
            "concert_se": concert_se,
            "user": user_id,
            "rank": idx,  # 1-based 순번
            "total": total,  # 현재 총 대기자 수
            "initial_total": initial_total,  # 진입 시점의 총 대기자 수
            "progress": round((initial_total - idx) / max(initial_total, 1) * 100, 2)  # 진행률 계산
        }
        
        # SSE로 순번 업데이트 전송
        await sse_manager.send(user_id, payload)
        
        # 로그: 백엔드에서 순번 푸시 내역 확인
        logger.info(f"SSE rank push -> user_id={user_id}, concert_se={concert_se}, rank={idx}, total={total}, initial_total={initial_total}")



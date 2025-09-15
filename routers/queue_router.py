"""
공연 대기열 관리 API 라우터

주요 기능:
- 사용자 대기열 진입/이탈 관리
- 실시간 순번 업데이트 (SSE)
- Kafka를 통한 이벤트 처리
- Redis ZSet을 이용한 FIFO 대기열 관리
"""

from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from utils.database import db_zump_async
from utils.sse import sse_manager
from utils.redis_client import RedisQueue
from utils.kafka_client import event_manager, EventTypes
from utils.config import config

import redis.asyncio as aioredis
from pydantic import BaseModel
import json
from confluent_kafka import Producer

# 전역 Redis 연결 (모든 API에서 공유)
redis_client = aioredis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)


# FastAPI 라우터 설정
router = APIRouter(prefix="/queue", tags=["queue"])


async def get_redis() -> aioredis.Redis:
    """Redis 연결 의존성 (현재는 전역 연결 사용)"""
    redis = aioredis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    await redis.ping()  # 연결 확인
    try:
        yield redis
    finally:
        await redis.close()


class QueuePayload(BaseModel):
    """대기열 API 요청 페이로드"""
    user_id: str


# Kafka Producer 설정 (concert_queue 토픽용)
kafka_producer = Producer({
    "bootstrap.servers": "localhost:9092"
})


@router.post("/enter/{concert_se}")
async def enter_queue(concert_se: str, payload: QueuePayload = Body(...), db: AsyncSession = Depends(db_zump_async)):
    """
    사용자를 공연 대기열에 진입시킴
    
    Args:
        concert_se: 공연 식별자
        payload: 사용자 ID가 포함된 요청 데이터
        
    Returns:
        현재 순번, 총 대기자 수, 진행률 등의 정보
    """
    user_id = payload.user_id

    # 1) 원자적 FIFO 순번 확정 (Redis INCR로 동시성 보장)
    zkey = f"queue:concert:{concert_se}"  # ZSet 키
    seq_key = f"queue:concert:{concert_se}:seq"  # 순번 카운터 키
    score = await redis_client.incr(seq_key)  # 원자적으로 증가하는 순번
    await redis_client.zadd(zkey, {user_id: float(score)})  # ZSet에 사용자 추가
    await redis_client.hset(f"queue:user:{user_id}:meta", mapping={"concert_se": concert_se, "initial_total": score})  # 사용자 메타데이터 저장

    # 2) Kafka 이벤트 발행 (순번 업데이트 브로드캐스트 트리거)
    message = {"action": "enter", "concert_se": concert_se, "user_id": user_id}
    kafka_producer.produce("concert_queue", key=user_id, value=json.dumps(message))
    kafka_producer.flush()

    # 3) 현재 상태 즉시 반환 (SSE 연결 전 초기 렌더링용)
    queue = RedisQueue(redis_client)
    total = await queue.get_count(concert_se)  # 현재 총 대기자 수
    rank = await queue.get_rank(concert_se, user_id)  # 현재 순번 (0-based)
    rank1 = (rank + 1) if rank is not None else None  # 1-based 순번으로 변환
    
    return {
        "concert_se": concert_se,
        "user_id": user_id,
        "rank": rank1,
        "total": total,
        "initial_total": score,  # 진입 시점의 총 대기자 수
        "progress": round((score - (rank1 or 0)) / max(score, 1) * 100, 2)  # 진행률 계산
    }


@router.post("/sse")
async def sse_stream(payload: QueuePayload = Body(...)):
    """
    사용자에게 실시간 순번 업데이트를 전송하는 SSE 스트림
    
    Args:
        payload: 사용자 ID가 포함된 요청 데이터
        
    Returns:
        Server-Sent Events 스트림
    """
    user_id = payload.user_id

    async def event_generator():
        """SSE 이벤트 생성기"""
        agen = sse_manager.connect(user_id)
        # 첫 메시지(connected) 전송
        first = await agen.__anext__()
        yield first
        
        # 부트스트랩: 현재 순번/총원 즉시 1회 푸시 (연결 직후 현재 상태 전송)
        try:
            queue = RedisQueue(redis_client)
            concert_se = await queue.get_user_concert_se(user_id)
            if concert_se:
                rank = await queue.get_rank(concert_se, user_id)
                total = await queue.get_count(concert_se)
                meta = await queue.get_user_meta(user_id) or {}
                initial_total = int(meta.get("initial_total", total))
                if rank is not None:
                    await sse_manager.send(user_id, {
                        "type": "rank",
                        "concert_se": concert_se,
                        "user": user_id,
                        "rank": rank + 1,
                        "total": total,
                        "progress": round((initial_total - (rank + 1)) / max(initial_total, 1) * 100, 2)
                    })
        except Exception:
            pass

        # SSE 스트림 전송
        async for chunk in agen:
            yield chunk
            
        # 연결 종료 콜백: 사용자 대기열에서 제거 (페이지 이탈 시)
        queue = RedisQueue(redis_client)
        concert_se = await queue.get_user_concert_se(user_id)
        if concert_se:
            await queue.remove_user(concert_se, user_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/leave/{concert_se}")
async def leave_queue(concert_se: str, payload: QueuePayload = Body(...)):
    """
    사용자를 공연 대기열에서 제거
    
    Args:
        concert_se: 공연 식별자
        payload: 사용자 ID가 포함된 요청 데이터
        
    Returns:
        이탈 완료 메시지
    """
    user_id = payload.user_id

    # concert_queue 토픽으로 대기열 이탈 요청 발행 (실제 제거는 워커에서 처리)
    message = {"action": "leave", "concert_se": concert_se, "user_id": user_id}
    kafka_producer.produce("concert_queue", key=user_id, value=json.dumps(message))
    kafka_producer.flush()

    return {"message": "left_queued"}


@router.get("/status/{concert_se}")
async def queue_status(concert_se: str, user_id: str):
    """
    사용자의 현재 순번/총원 스냅샷 조회 (폴링용)
    
    Args:
        concert_se: 공연 식별자
        user_id: 사용자 ID
        
    Returns:
        현재 순번, 총 대기자 수, 진행률 정보
    """
    queue = RedisQueue(redis_client)
    total = await queue.get_count(concert_se)  # 현재 총 대기자 수
    rank = await queue.get_rank(concert_se, user_id)  # 현재 순번 (0-based)
    rank1 = (rank + 1) if rank is not None else None  # 1-based 순번으로 변환
    
    return {
        "concert_se": concert_se,
        "user_id": user_id,
        "rank": rank1,
        "total": total,
        "percent": (round((0 if rank1 is None or total == 0 else (total - rank1) / max(total, 1) * 100), 2))  # 진행률 계산
    }



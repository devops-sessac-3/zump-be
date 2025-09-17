from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from utils.config import config
from utils.kafka_client import kafka_async
from utils.redis_client import redis_client


class EnqueueRequest(BaseModel):
    concert_se: str
    user_se: int


router = APIRouter(prefix="/queue", tags=["queue"])


@router.post(
    "/enqueue",
    summary="대기열 등록 이벤트를 Kafka로 전송",
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue(req: EnqueueRequest):
    try:
        topic = config.get_config("KAFKA")["QUEUE_TOPIC"]
        # FIFO를 돕기 위해 key를 concert별로 고정해 파티션-키를 유지
        key = f"concert:{req.concert_se}"
        value = f"{req.concert_se}|{req.user_se}"
        await kafka_async.send(topic=topic, value=value, key=key)
        # 옵션: 프로젝션 반영을 짧게 대기 후 실제 순번 반환 (기본 1500ms)
        wait_ms = int(os.getenv("ENQUEUE_PROJECTION_WAIT_MS", "1500"))
        deadline = asyncio.get_event_loop().time() + (wait_ms / 1000.0)
        r = redis_client.redis
        zkey = f"q:zset:{req.concert_se}"
        projected = False
        while True:
            rank = await r.zrank(zkey, str(req.user_se))
            total = await r.zcard(zkey)
            if rank is not None:
                projected = True
                return {
                    "status": "accepted",
                    "projected": projected,
                    "rank": rank + 1,
                    "total": total,
                }
            if asyncio.get_event_loop().time() >= deadline:
                break
            await asyncio.sleep(0.05)
        # 타임아웃 시 예상값 반환
        total = await r.zcard(zkey)
        return {
            "status": "accepted",
            "projected": projected,
            "rank": total + 1,
            "total": total + 1,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/status",
    summary="현재 순번/대기인원 조회",
    status_code=status.HTTP_200_OK,
)
async def queue_status(concert_se: str, user_se: int):
    try:
        r = redis_client.redis
        zkey = f"q:zset:{concert_se}"
        rank = await r.zrank(zkey, str(user_se))
        total = await r.zcard(zkey)
        return {
            "rank": (-1 if rank is None else rank + 1),
            "total": total,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


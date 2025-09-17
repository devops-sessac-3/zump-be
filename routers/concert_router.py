import asyncio

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from schemas import concert_schema as schema
from engines import concert_engine as engine
from utils.database import db_zump_async
from typing import List, Optional
from utils.config import config
from utils.kafka_client import kafka_async
from utils.queue_guard import ensure_queue_front
from utils.redis_client import redis_client
from utils import exception

_STATE_WAITING = "waiting"
_STATE_READY = "ready"

router = APIRouter()


async def _maybe_guard_concert_detail(concert_se: int, user_se: Optional[int]) -> None:
    """Auto-gate concert detail lookups when the queue threshold is exceeded."""
    queue_cfg = config.get_config("QUEUE") or {}
    gate_mode = str(queue_cfg.get("GATE_MODE", "")).lower()
    if gate_mode != "auto":
        return

    threshold = int(queue_cfg.get("AUTO_QUEUE_SIZE_THRESHOLD", 0) or 0)
    admit_window = int(queue_cfg.get("ADMIT_WINDOW", 1) or 1)
    wait_ms = int(queue_cfg.get("BLOCKING_DETAIL_WAIT_MS", 0) or 0)
    state_ttl = int(queue_cfg.get("AUTO_GATE_STATE_TTL_SEC", 30) or 30)

    r = redis_client.redis
    zkey = f"q:zset:{concert_se}"
    total = await r.zcard(zkey)
    rank = await r.zrank(zkey, str(user_se)) if user_se is not None else None
    state_key = f"q:gate:{concert_se}:{user_se}" if user_se is not None else None
    state = await r.get(state_key) if state_key else None

    if state == _STATE_READY:
        if state_key:
            await r.delete(state_key)
        return

    gate_active = (total >= threshold) or (rank is not None) or (state == _STATE_WAITING)
    if not gate_active:
        return

    if user_se is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USER_SE_REQUIRED", "message": "user_se query parameter is required when gate is active."},
        )

    if rank is None:
        kafka_cfg = config.get_config("KAFKA") or {}
        topic = kafka_cfg.get("QUEUE_TOPIC")
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "QUEUE_DISABLED", "message": "Kafka queue topic is not configured."},
            )

        value = f"{concert_se}|{user_se}"
        key = f"concert:{concert_se}"
        if state != _STATE_WAITING:
            await kafka_async.send(topic=topic, value=value, key=key)
            if state_key:
                await r.setex(state_key, state_ttl, _STATE_WAITING)

        if wait_ms > 0:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + (wait_ms / 1000.0)
            while loop.time() < deadline:
                await asyncio.sleep(0.05)
                rank = await r.zrank(zkey, str(user_se))
                if rank is not None:
                    if state_key:
                        await r.setex(state_key, state_ttl, _STATE_WAITING)
                    break
            total = await r.zcard(zkey)

    if rank is None:
        if state == _STATE_WAITING and state_key:
            await r.expire(state_key, state_ttl)
        total = await r.zcard(zkey)
        state = await r.get(state_key) if state_key else None
        if state == _STATE_READY:
            await r.delete(state_key)
            return
        total = await r.zcard(zkey)
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail={"code": "QUEUE_WAIT", "rank": total + 1, "total": total},
        )

    if admit_window < 1:
        admit_window = 1

    await ensure_queue_front(concert_se, user_se, window=admit_window)

@router.get(
    "/concerts",
    summary="콘서트 리스트 조회"
    , response_model=List[schema.concert]
    , responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get(
    req: Request
    , db: AsyncSession = Depends(db_zump_async)
):
    try:
        response = await engine.get_concerts(db)
        
        return response
    
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)

@router.get(
    "/concerts/{concert_se}",
    summary="콘서트 상세 조회"
    , response_model=List[schema.concert_detail]
    , responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_detail(
    req: Request
    , concert_se: int
    , user_se: Optional[int] = None
    , db: AsyncSession = Depends(db_zump_async)
):
    try:
        await _maybe_guard_concert_detail(concert_se, user_se)
        response = await engine.get_concert_detail(db, concert_se)
        return response
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)
    
@router.post(
    "/concerts-booking",
    summary="콘서트 예매"
    , response_model=List[schema.concerts_seat]
    , responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}   
)
async def post(
    req: Request
    , db: AsyncSession = Depends(db_zump_async)
    , payload: schema.payload_concert_booking = Body(
        description="콘서트 예매 요청 데이터",
        example={
            "user_se": "사용자일련번호",
            "concert_se": "공연일련번호",
            "seat_number": "좌석번호"
        }
    )
):
    try:
        response = await engine.post_concert_booking(db, payload)
        
        return response
    
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)
    

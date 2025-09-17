from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from utils.redis_client import redis_client


router = APIRouter(prefix="/queue", tags=["queue-sse"])


def _sse_format(event: str | None, data: str) -> str:
    if event:
        return f"event: {event}\ndata: {data}\n\n"
    return f"data: {data}\n\n"


async def _rank_payload(concert_se: str, user_se: int) -> str:
    r = redis_client.redis
    zkey = f"q:zset:{concert_se}"
    # rank는 0-based, UI는 1-based로 보정
    rank = await r.zrank(zkey, str(user_se))
    total = await r.zcard(zkey)
    now = datetime.utcnow().isoformat()
    return f"{{\"rank\": {(-1 if rank is None else rank + 1)}, \"total\": {total}, \"ts\": \"{now}\"}}"


async def _queue_stream(concert_se: str, user_se: int) -> AsyncIterator[bytes]:
    # 최초 스냅샷: 프로젝션 반영 대기 후 전송(옵션)
    wait_ms = int(os.getenv("SSE_SNAPSHOT_WAIT_MS", "1000"))
    if wait_ms > 0:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (wait_ms / 1000.0)
        r = redis_client.redis
        zkey = f"q:zset:{concert_se}"
        while True:
            rank = await r.zrank(zkey, str(user_se))
            if rank is not None or loop.time() >= deadline:
                break
            await asyncio.sleep(0.05)
    yield _sse_format("snapshot", await _rank_payload(concert_se, user_se)).encode("utf-8")

    # Pub/Sub 구독 채널
    channel = f"q:chn:{concert_se}"
    async for _ in redis_client.subscribe_iter(channel):
        yield _sse_format("update", await _rank_payload(concert_se, user_se)).encode("utf-8")


@router.get("/stream")
async def stream(concert_se: str, user_se: int, request: Request):
    async def event_generator():
        try:
            async for chunk in _queue_stream(concert_se, user_se):
                # 연결이 끊겼는지 확인
                if await request.is_disconnected():
                    break
                yield chunk
        except asyncio.CancelledError:
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream")


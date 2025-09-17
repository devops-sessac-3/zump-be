from __future__ import annotations

from fastapi import HTTPException, status

from utils.redis_client import redis_client


async def ensure_queue_front(concert_se: int | str, user_se: int, window: int = 1) -> None:
    """대기열 선두(window 이내)인지 확인. 아니면 HTTPException을 던진다.

    - window=1: 정확히 1등만 통과
    - rank는 0-based이므로 rank < window 조건이면 통과
    """
    r = redis_client.redis
    zkey = f"q:zset:{concert_se}"
    rank = await r.zrank(zkey, str(user_se))
    total = await r.zcard(zkey)

    if rank is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NOT_IN_QUEUE", "rank": -1, "total": total},
        )

    if rank >= window:
        # 425 Too Early: 아직 입장 시점 아님
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail={"code": "QUEUE_WAIT", "rank": rank + 1, "total": total},
        )





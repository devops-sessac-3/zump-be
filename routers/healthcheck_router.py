from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import db_zump_async
from utils.config import config
from utils.redis_client import redis_client  # ⬅️ NEW (위 1번 파일 경로에 맞게 import)

router = APIRouter(prefix="/health", tags=["healthcheck"])

# 시작 시간 기록
start_time = time.time()


async def get_db_session() -> AsyncSession:
    """데이터베이스 세션 의존성"""
    async with db_zump_async.session_local() as session:
        yield session


# ---------- 내부 헬퍼들 ----------

async def check_db(db: AsyncSession, timeout_sec: float = 2.0) -> dict:
    try:
        async with asyncio.timeout(timeout_sec):
            await db.execute(text("SELECT 1"))
        return {"status": "up"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def check_redis(timeout_sec: float = 2.0) -> dict:
    try:
        async with asyncio.timeout(timeout_sec):
            ok = await redis_client.ping()
            if not ok:
                return {"status": "down", "error": "PING failed"}
            # 짧은 echo 테스트(선택)
            key = "__health:redis__"
            now = datetime.utcnow().isoformat()
            await redis_client.redis.set(key, now, ex=5)
            val = await redis_client.redis.get(key)
        return {"status": "up", "echo": val}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def check_kafka(timeout_sec: float = 3.0) -> dict:
    """
    Kafka 메타데이터 조회로 연결성 확인.
    config 예시:
      KAFKA = {"BOOTSTRAP_SERVERS": "my-kafka.kafka.svc.cluster.local:9092"}
    """
    try:
        kafka_cfg = config.get_config("KAFKA")
        bootstrap = kafka_cfg.get("BOOTSTRAP_SERVERS") or kafka_cfg.get("BROKERS")
        if not bootstrap:
            return {"status": "down", "error": "missing KAFKA.BOOTSTRAP_SERVERS"}

        admin: Optional[AIOKafkaAdminClient] = None
        async with asyncio.timeout(timeout_sec):
            admin = AIOKafkaAdminClient(
                bootstrap_servers=bootstrap,
                request_timeout_ms=int(timeout_sec * 1000),
            )
            await admin.start()
            try:
                # 빠른 메타데이터/토픽 조회
                topics = await admin.list_topics()
                broker_count = len(admin._client.cluster.brokers())
            finally:
                await admin.close()

        return {
            "status": "up" if broker_count > 0 else "down",
            "brokers": broker_count,
            "topics_sample": list(topics)[:5] if topics else [],
        }
    except Exception as e:
        return {"status": "down", "error": str(e)}


# ---------- 엔드포인트들 ----------

@router.get(
    "/",
    summary="기본 Health Check",
    description="애플리케이션의 기본 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def health_check():
    uptime = time.time() - start_time
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "uptime": round(uptime, 2)
    }


@router.get(
    "/liveness",
    summary="Liveness Check",
    description="애플리케이션이 살아있는지 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def liveness_check():
    return {
        "status": "alive",
        "uptime": round(time.time() - start_time, 2)
    }


@router.get(
    "/readiness",
    summary="Readiness Check",
    description="DB/Redis/Kafka 연결 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def readiness_check(db: AsyncSession = Depends(get_db_session)):
    db_res, redis_res, kafka_res = await asyncio.gather(
        check_db(db),
        check_redis(),
        check_kafka(),
    )
    ready = all(x.get("status") == "up" for x in (db_res, redis_res, kafka_res))
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not-ready",
                "database": db_res,
                "redis": redis_res,
                "kafka": kafka_res,
            }
        )
    return {
        "status": "ready",
        "database": db_res,
        "redis": redis_res,
        "kafka": kafka_res,
    }


@router.get(
    "/db",
    summary="Database Health Check",
    description="데이터베이스 연결 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def database_health_check(db: AsyncSession = Depends(get_db_session)):
    res = await check_db(db)
    if res["status"] != "up":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {res.get('error')}"
        )
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": datetime.now().isoformat()
    }


@router.get(
    "/redis",
    summary="Redis Health Check",
    description="Redis 연결 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def redis_health_check():
    res = await check_redis()
    if res["status"] != "up":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"redis": res}
        )
    return {"status": "healthy", "redis": res}


@router.get(
    "/kafka",
    summary="Kafka Health Check",
    description="Kafka 연결 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def kafka_health_check():
    res = await check_kafka()
    if res["status"] != "up":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"kafka": res}
        )
    return {"status": "healthy", "kafka": res}


@router.get(
    "/stack",
    summary="전체 스택 Health Check",
    description="DB/Redis/Kafka를 모두 점검합니다.",
    status_code=status.HTTP_200_OK
)
async def stack_health_check(db: AsyncSession = Depends(get_db_session)):
    db_res, redis_res, kafka_res = await asyncio.gather(
        check_db(db),
        check_redis(),
        check_kafka(),
    )
    overall = "healthy" if all(r.get("status") == "up" for r in (db_res, redis_res, kafka_res)) else "degraded"
    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": db_res,
            "redis": redis_res,
            "kafka": kafka_res,
        }
    }

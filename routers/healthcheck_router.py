import time
from datetime import datetime

from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import db_zump_async

router = APIRouter(prefix="/health", tags=["healthcheck"])

# 시작 시간 기록
start_time = time.time()


async def get_db_session() -> AsyncSession:
    """데이터베이스 세션 의존성"""
    async with db_zump_async.session_local() as session:
        yield session


@router.get(
    "/",
    summary="기본 Health Check",
    description="애플리케이션의 기본 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    기본 healthcheck 엔드포인트
    애플리케이션이 실행 중인지 확인합니다.
    """
    uptime = time.time() - start_time
    
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "uptime": round(uptime, 2)
    }


@router.get(
    "/readiness",
    summary="Readiness Check",
    description="데이터베이스 연결 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def readiness_check(db: AsyncSession = Depends(get_db_session)):
    """
    Readiness 체크 엔드포인트
    데이터베이스 연결 상태를 확인합니다.
    """
    try:
        # 간단한 쿼리로 DB 연결 확인
        await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )


@router.get(
    "/liveness",
    summary="Liveness Check",
    description="애플리케이션이 살아있는지 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def liveness_check():
    """
    Liveness 체크 엔드포인트
    애플리케이션이 응답하는지 확인합니다.
    """
    return {
        "status": "alive",
        "uptime": round(time.time() - start_time, 2)
    }


@router.get(
    "/db",
    summary="Database Health Check",
    description="데이터베이스 연결 상태를 확인합니다.",
    status_code=status.HTTP_200_OK
)
async def database_health_check(db: AsyncSession = Depends(get_db_session)):
    """
    데이터베이스 healthcheck 엔드포인트
    데이터베이스 연결 상태를 확인합니다.
    """
    try:
        # 간단한 쿼리로 DB 연결 확인
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )

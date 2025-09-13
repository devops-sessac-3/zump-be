"""
SSE (Server Sent Event) 전용 라우터
실시간 좌석 상태 업데이트를 위한 SSE 엔드포인트
"""
import uuid
from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from utils import exception
from utils.sse_manager import sse_streamer, sse_manager
from typing import Optional

router = APIRouter()

@router.get(
    "/sse/events",
    summary="실시간 이벤트 스트림 (전체)",
    description="모든 좌석 상태 변경 이벤트를 실시간으로 수신합니다.",
    responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_all_events(
    req: Request,
    client_id: Optional[str] = Query(None, description="클라이언트 ID (자동 생성됨)")
):
    """전체 좌석 이벤트 스트림"""
    try:
        if not client_id:
            client_id = str(uuid.uuid4())
        
        return await sse_streamer.create_stream(client_id)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SSE 스트림 생성 실패: {str(e)}"
        )

@router.get(
    "/sse/events/concerts/{concert_se}",
    summary="공연별 실시간 이벤트 스트림",
    description="특정 공연의 좌석 상태 변경 이벤트를 실시간으로 수신합니다.",
    responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_concert_events(
    req: Request,
    concert_se: int,
    client_id: Optional[str] = Query(None, description="클라이언트 ID (자동 생성됨)")
):
    """특정 공연의 좌석 이벤트 스트림"""
    try:
        if not client_id:
            client_id = str(uuid.uuid4())
        
        return await sse_streamer.create_stream(client_id, concert_se=concert_se)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SSE 스트림 생성 실패: {str(e)}"
        )

@router.get(
    "/sse/events/concerts/{concert_se}/seats/{seat_number}",
    summary="좌석별 실시간 이벤트 스트림",
    description="특정 좌석의 상태 변경 이벤트를 실시간으로 수신합니다.",
    responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_seat_events(
    req: Request,
    concert_se: int,
    seat_number: int,
    client_id: Optional[str] = Query(None, description="클라이언트 ID (자동 생성됨)")
):
    """특정 좌석의 이벤트 스트림"""
    try:
        if not client_id:
            client_id = str(uuid.uuid4())
        
        return await sse_streamer.create_stream(
            client_id, 
            concert_se=concert_se, 
            seat_number=seat_number
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SSE 스트림 생성 실패: {str(e)}"
        )

@router.get(
    "/sse/stats",
    summary="SSE 연결 통계",
    description="현재 SSE 연결 상태 및 통계를 조회합니다.",
    responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_sse_stats(req: Request):
    """SSE 연결 통계 조회"""
    try:
        total_clients = await sse_manager.get_client_count()
        
        stats = {
            "total_connections": total_clients,
            "concert_subscriptions": len(sse_manager.concert_subscriptions),
            "seat_subscriptions": len(sse_manager.seat_subscriptions),
            "timestamp": __import__('time').time()
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SSE 통계 조회 실패: {str(e)}"
        )

@router.get(
    "/sse/stats/concerts/{concert_se}",
    summary="공연별 SSE 연결 통계",
    description="특정 공연의 SSE 구독자 수를 조회합니다.",
    responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_concert_sse_stats(
    req: Request,
    concert_se: int
):
    """공연별 SSE 구독자 통계"""
    try:
        subscribers = await sse_manager.get_concert_subscribers(concert_se)
        
        stats = {
            "concert_se": concert_se,
            "subscribers": subscribers,
            "timestamp": __import__('time').time()
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"공연별 SSE 통계 조회 실패: {str(e)}"
        )

@router.get(
    "/sse/stats/concerts/{concert_se}/seats/{seat_number}",
    summary="좌석별 SSE 연결 통계",
    description="특정 좌석의 SSE 구독자 수를 조회합니다.",
    responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_seat_sse_stats(
    req: Request,
    concert_se: int,
    seat_number: int
):
    """좌석별 SSE 구독자 통계"""
    try:
        subscribers = await sse_manager.get_seat_subscribers(concert_se, seat_number)
        
        stats = {
            "concert_se": concert_se,
            "seat_number": seat_number,
            "subscribers": subscribers,
            "timestamp": __import__('time').time()
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"좌석별 SSE 통계 조회 실패: {str(e)}"
        )

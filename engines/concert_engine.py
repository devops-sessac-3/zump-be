from fastapi import status, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from schemas import concert_schema as schema
from queries import concert_query as query
from utils.database import execute_query_async
from utils.database import execute_post_async
from utils.redis_client import cache_manager
from engines.seat_engine import seat_engine
from utils import messsage
from utils import json_util


async def get_concerts(db: AsyncSession):
    """공연 목록 조회 (캐시 우선)"""
    cache_key = "concerts:list"
    
    # 캐시에서 조회
    cached_concerts = await cache_manager.get_cached_data(cache_key)
    if cached_concerts:
        return cached_concerts
    
    # DB에서 조회
    sql_query, params = query.get_concerts()
    result_list = await execute_query_async(db, sql=sql_query, params=params, schema=schema.concert)
    
    # 캐시에 저장 (10분)
    await cache_manager.set_cached_data(cache_key, [concert.dict() for concert in result_list], expire=600)
    
    return result_list

async def get_concert_detail(db: AsyncSession, concert_se: int):
    sql_query, params = query.get_concert_detail(concert_se)
    result_list = await execute_query_async(db, sql=sql_query, params=params, schema=schema.concert_detail)

    return result_list

async def get_concert_seats(db: AsyncSession, concert_se: int):
    """공연 좌석 상태 조회"""
    try:
        seats = await seat_engine.get_concert_seats(db, concert_se)
        return seats
    except Exception as e:
        print(f"좌석 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="좌석 상태 조회 중 오류가 발생했습니다."
        )

async def get_seat_state(db: AsyncSession, concert_se: int, seat_number: int):
    """특정 좌석 상태 조회"""
    try:
        seat_state = await seat_engine.get_seat_state(db, concert_se, seat_number)
        if not seat_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="좌석을 찾을 수 없습니다."
            )
        return seat_state
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"좌석 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="좌석 상태 조회 중 오류가 발생했습니다."
        )
    
async def post_concert_booking(db: AsyncSession, payload: schema.payload_concert_booking):
    """콘서트 예매 (분산 락 사용)"""
    try:
        # 좌석 상태 엔진을 사용한 안전한 예매
        booking_result = await seat_engine.book_seat(
            db=db,
            user_se=payload.user_se,
            concert_se=payload.concert_se,
            seat_number=payload.seat_number
        )
        
        # 공연 목록 캐시 무효화
        await cache_manager.invalidate_pattern("concerts:*")
        
        return {
            "message": "예매가 완료되었습니다.",
            "booking_info": booking_result
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"예매 처리 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="예매 처리 중 오류가 발생했습니다."
        )
    
    

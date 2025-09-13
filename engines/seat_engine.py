"""
좌석 상태 관리 엔진
분산 락을 사용한 좌석 예매 동시성 제어
"""
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from utils.redis_client import DistributedLock, redis_client, cache_manager
from utils.kafka_client import event_manager, EventTypes
from utils.database import execute_query_async, execute_post_async
from schemas import concert_schema as schema
from queries import concert_query as query
import json


class SeatStateEngine:
    """좌석 상태 관리 엔진"""
    
    def __init__(self):
        self.cache_prefix = "seat_state"
        self.lock_timeout = 30  # 30초 락 타임아웃
    
    async def get_seat_state(self, db: AsyncSession, concert_se: int, seat_number: int) -> Optional[Dict[str, Any]]:
        """좌석 상태 조회 (캐시 우선)"""
        cache_key = f"{self.cache_prefix}:{concert_se}:{seat_number}"
        
        # 캐시에서 조회
        cached_state = await cache_manager.get_cached_data(cache_key)
        if cached_state:
            return cached_state
        
        # DB에서 조회
        db_state = await self._get_seat_state_from_db(db, concert_se, seat_number)
        if db_state:
            # 캐시에 저장 (5분)
            await cache_manager.set_cached_data(cache_key, db_state, expire=300)
        
        return db_state
    
    async def _get_seat_state_from_db(self, db: AsyncSession, concert_se: int, seat_number: int) -> Optional[Dict[str, Any]]:
        """DB에서 좌석 상태 조회"""
        sql = """
        SELECT 
            s.seat_se,
            s.seat_number,
            s.is_booked,
            s.concert_se,
            c.concert_name,
            c.concert_date,
            c.concert_time
        FROM concerts_seat s
        INNER JOIN concerts c ON s.concert_se = c.concert_se
        WHERE s.concert_se = :concert_se AND s.seat_number = :seat_number
        """
        
        params = {"concert_se": concert_se, "seat_number": seat_number}
        
        try:
            from sqlalchemy import text
            result = await db.execute(text(sql), params)
            row = result.fetchone()
            
            if row:
                return {
                    "seat_se": row.seat_se,
                    "seat_number": row.seat_number,
                    "is_booked": row.is_booked,
                    "concert_se": row.concert_se,
                    "concert_name": row.concert_name,
                    "concert_date": str(row.concert_date),
                    "concert_time": str(row.concert_time)
                }
        except Exception as e:
            print(f"좌석 상태 조회 실패: {e}")
        
        return None
    
    async def get_concert_seats(self, db: AsyncSession, concert_se: int) -> List[Dict[str, Any]]:
        """공연의 모든 좌석 상태 조회"""
        cache_key = f"{self.cache_prefix}:concert:{concert_se}"
        
        # 캐시에서 조회
        cached_seats = await cache_manager.get_cached_data(cache_key)
        if cached_seats:
            return cached_seats
        
        # DB에서 조회
        sql = """
        SELECT 
            s.seat_se,
            s.seat_number,
            s.is_booked,
            s.concert_se
        FROM concerts_seat s
        WHERE s.concert_se = :concert_se
        ORDER BY s.seat_number
        """
        
        params = {"concert_se": concert_se}
        
        try:
            from sqlalchemy import text
            result = await db.execute(text(sql), params)
            
            seats = []
            for row in result:
                seats.append({
                    "seat_se": row.seat_se,
                    "seat_number": row.seat_number,
                    "is_booked": row.is_booked,
                    "concert_se": row.concert_se
                })
            
            # 캐시에 저장 (5분)
            await cache_manager.set_cached_data(cache_key, seats, expire=300)
            return seats
            
        except Exception as e:
            print(f"공연 좌석 조회 실패: {e}")
            return []
    
    async def book_seat(self, db: AsyncSession, user_se: int, concert_se: int, seat_number: int) -> Dict[str, Any]:
        """좌석 예매 (분산 락 사용)"""
        lock_key = f"seat_booking:{concert_se}:{seat_number}"
        
        async with DistributedLock(redis_client, lock_key, self.lock_timeout):
            # 1. 좌석 상태 재확인
            seat_state = await self.get_seat_state(db, concert_se, seat_number)
            if not seat_state:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="좌석을 찾을 수 없습니다."
                )
            
            if seat_state["is_booked"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 예매된 좌석입니다."
                )
            
            # 2. 좌석 예매 처리
            try:
                # 트랜잭션 시작
                async with db.begin():
                    # 좌석 상태 업데이트
                    update_seat_sql = """
                    UPDATE concerts_seat 
                    SET is_booked = true 
                    WHERE concert_se = :concert_se AND seat_number = :seat_number
                    """
                    await db.execute(text(update_seat_sql), {
                        "concert_se": concert_se,
                        "seat_number": seat_number
                    })
                    
                    # 예매 기록 생성
                    booking_sql = """
                    INSERT INTO concert_booking (user_se, concert_se, seat_number)
                    VALUES (:user_se, :concert_se, :seat_number)
                    RETURNING booking_se, create_dt
                    """
                    result = await db.execute(text(booking_sql), {
                        "user_se": user_se,
                        "concert_se": concert_se,
                        "seat_number": seat_number
                    })
                    
                    booking_record = result.fetchone()
                    
                    # 3. 캐시 무효화
                    await self._invalidate_seat_cache(concert_se, seat_number)
                    
                    # 4. 이벤트 발행
                    await self._publish_seat_event(
                        event_type=EventTypes.SEAT_BOOKED,
                        concert_se=concert_se,
                        seat_number=seat_number,
                        user_se=user_se,
                        booking_se=booking_record.booking_se
                    )
                    
                    return {
                        "booking_se": booking_record.booking_se,
                        "user_se": user_se,
                        "concert_se": concert_se,
                        "seat_number": seat_number,
                        "is_booked": True,
                        "create_dt": str(booking_record.create_dt)
                    }
                    
            except Exception as e:
                print(f"좌석 예매 실패: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="좌석 예매 중 오류가 발생했습니다."
                )
    
    async def cancel_booking(self, db: AsyncSession, booking_se: int, user_se: int) -> bool:
        """예매 취소"""
        # 예매 정보 조회
        booking_sql = """
        SELECT booking_se, user_se, concert_se, seat_number
        FROM concert_booking
        WHERE booking_se = :booking_se AND user_se = :user_se
        """
        
        result = await db.execute(text(booking_sql), {
            "booking_se": booking_se,
            "user_se": user_se
        })
        
        booking = result.fetchone()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="예매 정보를 찾을 수 없습니다."
            )
        
        lock_key = f"seat_booking:{booking.concert_se}:{booking.seat_number}"
        
        async with DistributedLock(redis_client, lock_key, self.lock_timeout):
            try:
                async with db.begin():
                    # 예매 기록 삭제
                    delete_booking_sql = """
                    DELETE FROM concert_booking
                    WHERE booking_se = :booking_se
                    """
                    await db.execute(text(delete_booking_sql), {
                        "booking_se": booking_se
                    })
                    
                    # 좌석 상태 복원
                    update_seat_sql = """
                    UPDATE concerts_seat 
                    SET is_booked = false 
                    WHERE concert_se = :concert_se AND seat_number = :seat_number
                    """
                    await db.execute(text(update_seat_sql), {
                        "concert_se": booking.concert_se,
                        "seat_number": booking.seat_number
                    })
                    
                    # 캐시 무효화
                    await self._invalidate_seat_cache(booking.concert_se, booking.seat_number)
                    
                    # 이벤트 발행
                    await self._publish_seat_event(
                        event_type=EventTypes.SEAT_CANCELLED,
                        concert_se=booking.concert_se,
                        seat_number=booking.seat_number,
                        user_se=user_se,
                        booking_se=booking_se
                    )
                    
                    return True
                    
            except Exception as e:
                print(f"예매 취소 실패: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="예매 취소 중 오류가 발생했습니다."
                )
    
    async def _invalidate_seat_cache(self, concert_se: int, seat_number: int):
        """좌석 관련 캐시 무효화"""
        # 특정 좌석 캐시 삭제
        seat_cache_key = f"{self.cache_prefix}:{concert_se}:{seat_number}"
        await cache_manager.redis.delete(seat_cache_key)
        
        # 공연 전체 좌석 캐시 삭제
        concert_cache_key = f"{self.cache_prefix}:concert:{concert_se}"
        await cache_manager.redis.delete(concert_cache_key)
    
    async def update_seat_state(self, concert_se: int, seat_number: int, is_booked: bool):
        """좌석 상태 업데이트 (관리자용)"""
        lock_key = f"seat_booking:{concert_se}:{seat_number}"
        
        async with DistributedLock(redis_client, lock_key, self.lock_timeout):
            # DB 업데이트
            sql = """
            UPDATE concerts_seat 
            SET is_booked = :is_booked 
            WHERE concert_se = :concert_se AND seat_number = :seat_number
            """
            
            # 여기서는 DB 세션을 직접 받지 않으므로 별도 처리 필요
            # 실제 구현에서는 DB 세션을 받아서 처리
            
            # 캐시 무효화
            await self._invalidate_seat_cache(concert_se, seat_number)
    
    async def _publish_seat_event(self, event_type: str, concert_se: int, seat_number: int, 
                                 user_se: int = None, booking_se: int = None, is_booked: bool = None):
        """좌석 관련 이벤트 발행"""
        try:
            event_data = {
                "event_type": event_type,
                "concert_se": concert_se,
                "seat_number": seat_number,
                "user_se": user_se,
                "booking_se": booking_se,
                "is_booked": is_booked,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # 좌석 상태 변경 이벤트 발행
            await event_manager.publish_event(
                topic="seat_events",
                event=event_data,
                key=f"{concert_se}:{seat_number}"
            )
            
            print(f"좌석 이벤트 발행: {event_type} - {concert_se}:{seat_number}")
            
        except Exception as e:
            print(f"이벤트 발행 실패: {e}")


# 전역 좌석 상태 엔진 인스턴스
seat_engine = SeatStateEngine()

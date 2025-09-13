"""
ZUMP API 테스트용 버전 (Redis 포함)
Python 3.13.7 호환성 문제 해결을 위한 Redis 기능 포함 API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import asyncio
import time

app = FastAPI(
    title="ZUMP API (Test Version with Redis)",
    description="ZUMP REST API - Redis 기능 포함 테스트용",
    version="0.0.1"
)

# 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 스키마 정의
class Concert(BaseModel):
    concert_se: int
    concert_name: str
    concert_date: str
    concert_time: str
    concert_price: int
    concert_description: Optional[str] = None
    concert_venue: str

class Seat(BaseModel):
    seat_se: int
    seat_number: str
    is_booked: bool
    concert_se: int

class BookingRequest(BaseModel):
    user_se: int
    concert_se: int
    seat_number: str

# 메모리 데이터 (실제로는 DB 사용)
concerts_data = [
    {
        "concert_se": 1,
        "concert_name": "2024 봄 콘서트",
        "concert_date": "2024-04-15",
        "concert_time": "19:00:00",
        "concert_price": 50000,
        "concert_description": "봄의 감성을 담은 특별한 콘서트",
        "concert_venue": "올림픽공원 KSPO DOME"
    },
    {
        "concert_se": 2,
        "concert_name": "여름 페스티벌",
        "concert_date": "2024-07-20",
        "concert_time": "20:00:00",
        "concert_price": 70000,
        "concert_description": "여름의 열정이 담긴 페스티벌",
        "concert_venue": "잠실 실내체육관"
    }
]

seats_data = {
    1: [  # concert_se = 1
        {"seat_se": 1, "seat_number": "A1", "is_booked": False, "concert_se": 1},
        {"seat_se": 2, "seat_number": "A2", "is_booked": False, "concert_se": 1},
        {"seat_se": 3, "seat_number": "A3", "is_booked": True, "concert_se": 1},
        {"seat_se": 4, "seat_number": "B1", "is_booked": False, "concert_se": 1},
        {"seat_se": 5, "seat_number": "B2", "is_booked": False, "concert_se": 1},
    ],
    2: [  # concert_se = 2
        {"seat_se": 6, "seat_number": "A1", "is_booked": False, "concert_se": 2},
        {"seat_se": 7, "seat_number": "A2", "is_booked": False, "concert_se": 2},
        {"seat_se": 8, "seat_number": "A3", "is_booked": False, "concert_se": 2},
    ]
}

# 간단한 분산 락 시뮬레이션 (메모리 기반)
class SimpleDistributedLock:
    def __init__(self):
        self.locks = {}
    
    async def acquire(self, lock_key: str, timeout: int = 30) -> bool:
        """락 획득 시도"""
        current_time = time.time()
        
        # 기존 락이 있고 아직 유효한지 확인
        if lock_key in self.locks:
            lock_time, lock_id = self.locks[lock_key]
            if current_time - lock_time < timeout:
                return False  # 락이 이미 존재함
        
        # 락 획득
        self.locks[lock_key] = (current_time, f"lock_{current_time}")
        return True
    
    async def release(self, lock_key: str):
        """락 해제"""
        if lock_key in self.locks:
            del self.locks[lock_key]

# 전역 락 인스턴스
distributed_lock = SimpleDistributedLock()

# API 엔드포인트
@app.get("/")
async def root():
    return {"message": "ZUMP API 테스트 서버가 실행 중입니다! (Redis 기능 포함)"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "ZUMP API is running"}

@app.get("/concerts", response_model=List[Concert])
async def get_concerts():
    """공연 목록 조회 (캐시 시뮬레이션)"""
    # 실제로는 Redis에서 캐시 조회
    print("공연 목록 조회 (캐시 시뮬레이션)")
    return concerts_data

@app.get("/concerts/{concert_se}", response_model=Concert)
async def get_concert_detail(concert_se: int):
    """공연 상세 조회"""
    for concert in concerts_data:
        if concert["concert_se"] == concert_se:
            return concert
    raise HTTPException(status_code=404, detail="공연을 찾을 수 없습니다.")

@app.get("/concerts/{concert_se}/seats", response_model=List[Seat])
async def get_concert_seats(concert_se: int):
    """공연 좌석 상태 조회 (캐시 시뮬레이션)"""
    if concert_se not in seats_data:
        raise HTTPException(status_code=404, detail="공연을 찾을 수 없습니다.")
    
    print(f"좌석 상태 조회 (캐시 시뮬레이션): {concert_se}")
    return seats_data[concert_se]

@app.get("/concerts/{concert_se}/seats/{seat_number}", response_model=Seat)
async def get_seat_state(concert_se: int, seat_number: str):
    """특정 좌석 상태 조회"""
    if concert_se not in seats_data:
        raise HTTPException(status_code=404, detail="공연을 찾을 수 없습니다.")
    
    for seat in seats_data[concert_se]:
        if seat["seat_number"] == seat_number:
            return seat
    raise HTTPException(status_code=404, detail="좌석을 찾을 수 없습니다.")

@app.post("/concerts-booking")
async def book_concert(booking: BookingRequest):
    """콘서트 예매 (분산 락 시뮬레이션)"""
    concert_se = booking.concert_se
    seat_number = booking.seat_number
    lock_key = f"seat_booking:{concert_se}:{seat_number}"
    
    # 분산 락 획득 시도
    lock_acquired = await distributed_lock.acquire(lock_key, timeout=30)
    if not lock_acquired:
        raise HTTPException(status_code=409, detail="다른 사용자가 처리 중입니다. 잠시 후 다시 시도해주세요.")
    
    try:
        if concert_se not in seats_data:
            raise HTTPException(status_code=404, detail="공연을 찾을 수 없습니다.")
        
        # 좌석 찾기
        seat_found = False
        for seat in seats_data[concert_se]:
            if seat["seat_number"] == seat_number:
                seat_found = True
                if seat["is_booked"]:
                    raise HTTPException(status_code=409, detail="이미 예매된 좌석입니다.")
                else:
                    seat["is_booked"] = True
                    break
        
        if not seat_found:
            raise HTTPException(status_code=404, detail="좌석을 찾을 수 없습니다.")
        
        # 이벤트 발행 시뮬레이션
        event_data = {
            "event_type": "seat_booked",
            "concert_se": concert_se,
            "seat_number": seat_number,
            "user_se": booking.user_se,
            "timestamp": time.time()
        }
        print(f"이벤트 발행 시뮬레이션: {event_data}")
        
        return {
            "message": "예매가 완료되었습니다.",
            "booking_info": {
                "user_se": booking.user_se,
                "concert_se": booking.concert_se,
                "seat_number": booking.seat_number,
                "is_booked": True
            },
            "event_published": True
        }
    
    finally:
        # 락 해제
        await distributed_lock.release(lock_key)

@app.get("/concerts/{concert_se}/seats/{seat_number}/book")
async def book_seat_direct(concert_se: int, seat_number: str, user_se: int = 1):
    """직접 좌석 예매 (URL 파라미터)"""
    lock_key = f"seat_booking:{concert_se}:{seat_number}"
    
    # 분산 락 획득 시도
    lock_acquired = await distributed_lock.acquire(lock_key, timeout=30)
    if not lock_acquired:
        raise HTTPException(status_code=409, detail="다른 사용자가 처리 중입니다. 잠시 후 다시 시도해주세요.")
    
    try:
        if concert_se not in seats_data:
            raise HTTPException(status_code=404, detail="공연을 찾을 수 없습니다.")
        
        # 좌석 찾기
        seat_found = False
        for seat in seats_data[concert_se]:
            if seat["seat_number"] == seat_number:
                seat_found = True
                if seat["is_booked"]:
                    raise HTTPException(status_code=409, detail="이미 예매된 좌석입니다.")
                else:
                    seat["is_booked"] = True
                    break
        
        if not seat_found:
            raise HTTPException(status_code=404, detail="좌석을 찾을 수 없습니다.")
        
        return {
            "message": "예매가 완료되었습니다.",
            "booking_info": {
                "user_se": user_se,
                "concert_se": concert_se,
                "seat_number": seat_number,
                "is_booked": True
            }
        }
    
    finally:
        # 락 해제
        await distributed_lock.release(lock_key)

@app.get("/locks/status")
async def get_lock_status():
    """현재 락 상태 조회"""
    return {
        "active_locks": len(distributed_lock.locks),
        "locks": list(distributed_lock.locks.keys())
    }

@app.post("/locks/clear")
async def clear_all_locks():
    """모든 락 해제 (관리자용)"""
    distributed_lock.locks.clear()
    return {"message": "모든 락이 해제되었습니다."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

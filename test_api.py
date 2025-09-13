"""
ZUMP API 테스트용 최소 버전
Python 3.13 호환성 문제 해결을 위한 간단한 API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json

app = FastAPI(
    title="ZUMP API (Test Version)",
    description="ZUMP REST API - 테스트용",
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

# API 엔드포인트
@app.get("/")
async def root():
    return {"message": "ZUMP API 테스트 서버가 실행 중입니다!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "ZUMP API is running"}

@app.get("/concerts", response_model=List[Concert])
async def get_concerts():
    """공연 목록 조회"""
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
    """공연 좌석 상태 조회"""
    if concert_se not in seats_data:
        raise HTTPException(status_code=404, detail="공연을 찾을 수 없습니다.")
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
    """콘서트 예매 (간단한 동시성 제어 없음)"""
    concert_se = booking.concert_se
    seat_number = str(booking.seat_number)
    
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
            "user_se": booking.user_se,
            "concert_se": booking.concert_se,
            "seat_number": booking.seat_number,
            "is_booked": True
        }
    }

@app.get("/concerts/{concert_se}/seats/{seat_number}/book")
async def book_seat_direct(concert_se: int, seat_number: str, user_se: int = 1):
    """직접 좌석 예매 (URL 파라미터)"""
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

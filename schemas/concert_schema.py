from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, time, datetime


class concert(BaseModel):
    concert_se: int = Field(..., description="콘서트 일년번호")
    concert_name: str = Field(..., description="공연 제목")
    concert_date: date = Field(..., description="공연 날짜")
    concert_time: time = Field(..., description="공연 시간")
    concert_price: int = Field(..., description="공연 가격")
    concert_description: str = Field(default=None, description="공연 설명")
    concert_venue: str = Field(..., description="공연 장소")

    class Config:
        from_attributes = True
        
class concerts_seat(BaseModel):
    seat_se: int = Field(..., description="좌석 일련번호")
    seat_number: str = Field(..., description="좌석 번호")
    is_booked: bool = Field(..., description="좌석 사용 가능 여부")

    class Config:
        from_attributes = True

class concert_detail(BaseModel):
    booking_se: int = Field(..., description="예매 일련번호")
    user_se: int    = Field(..., description="사용자 일련번호")
    user_name: str  = Field(..., description="사용자 이름")
    user_email: str = Field(..., description="사용자 이메일")
    concert_se: int     = Field(..., description="콘서트 일련번호")
    concert_name: str       = Field(..., description="공연 제목")
    concert_date: date      = Field(..., description="공연 날짜")
    concert_time: time      = Field(..., description="공연 시간")
    concert_price: Optional[int]        = Field(None, description="공연 가격")
    concert_description: Optional[str]      = Field(None, description="공연 설명")
    concert_venue: Optional[str]    = Field(None, description="공연 장소")
    seat_se: int        = Field(..., description="좌석 일련번호")
    seat_number: str    = Field(..., description="좌석 번호")
    is_booked: str      = Field(..., description="좌석 사용 가능 여부")
    create_dt: datetime     = Field(..., description="예매 생성 일시")
                               
    class Config:
        from_attributes = True
131
class payload_concert_booking(BaseModel):
    user_se: int = Field(..., description="예매자 일련번호")
    concert_se: int = Field(..., description="예매 공연 일련번호")
    seat_number: int = Field(..., description="예매 좌석 번호")

    class Config:
        from_attributes = True


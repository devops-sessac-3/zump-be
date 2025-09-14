from fastapi import APIRouter, HTTPException, Request, Depends, Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from utils import exception
from schemas import concert_schema as schema
from engines import concert_engine as engine
from utils import exception
from utils.database import db_zump_async
from typing import List
 
router = APIRouter()

@router.get(
    "/concerts",
    summary="콘서트 리스트 조회"
    , response_model=List[schema.concert]
    , responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get(
    req: Request
    , db: AsyncSession = Depends(db_zump_async)
):
    try:
        response = await engine.get_concerts(db)
        
        return response
    
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)

@router.get(
    "/concerts/{consert_se}",
    summary="콘서트 상세 조회"
    , response_model=List[schema.concert_detail]
    , responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}
)
async def get_detail(
    req: Request
    , concert_se: int
    , db: AsyncSession = Depends(db_zump_async)
):
    try:
        response = await engine.get_concert_detail(db, concert_se)
        return response
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)
    
@router.post(
    "/concerts-booking",
    summary="콘서트 예매"
    , response_model=List[schema.concerts_seat]
    , responses={**(exception.get_responses([200, 400, 401, 403, 404, 500]))}   
)
async def post(
    req: Request
    , db: AsyncSession = Depends(db_zump_async)
    , payload: schema.payload_concert_booking = Body(
        description="콘서트 예매 요청 데이터",
        example={
            "user_se": "사용자일련번호",
            "concert_se": "공연일련번호",
            "seat_number": "좌석번호"
        }
    )
):
    try:
        response = await engine.post_concert_booking(db, payload)
        
        return response
    
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)
    

from fastapi import APIRouter, HTTPException, status, Request, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from utils import exception
from schemas import user_schema as schema
from engines import user_engine as engine
from utils.database import db_zump_async

router = APIRouter()

@router.post(
    "/auth/signup"
    , summary="회원가입"
    , description="회원가입"
    , responses={**(exception.get_responses([201, 400, 401, 403, 404, 500]))}
)
async def post(
    req: Request
    , db: AsyncSession = Depends(db_zump_async)
    , payload: schema.payload_user_signup = Body(
        description="회원가입 정보",
        example={
            "user_email": "이메일"
            , "user_password": "비밀번호"
        }
    )
):
    try:
        response = await engine.post_user_signup(db, payload=payload)
        
        return response
    
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)

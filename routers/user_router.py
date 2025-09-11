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
            , "user_name": "이름"
        }
    )
):
    try:
        response = await engine.post_user_signup(db, payload=payload)
        
        return response
    
    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)
    
@router.post(
    "/auth/login"
    , summary="로그인"
    , description="로그인(access_token, refresh_token 발급)"
    , responses={**(exception.get_responses([200, 400, 401,403, 404, 500]))}
)
async def post(
    req: Request
    , db: AsyncSession = Depends(db_zump_async)
    , payload: schema.payload_user_signup = Body(
        description="로그인 정보",
        example={
            "user_email": "이메일"
            , "user_password": "비밀번호"
        }
    )
):
    try:
        # 로그인: 이메일/비밀번호 기반
        user_id = payload.user_email
        user_pw = payload.user_password

        # 1. 사용자 조회       # 2. 비밀번호 검증  # 3. 토큰 발급
        response = await engine.post_user_login(db, user_id, user_pw)
        return response

    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)
    except Exception as ex:
        return await exception.handle_exception(ex, req, __file__)

from fastapi import APIRouter, HTTPException, status, Request, Depends, Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from utils import exception
from schemas import user_schema as schema
from engines import user_engine as engine
from utils import exception, security
from utils.config import config
# from utils.oauth import oauth
from utils.database import db_zump_async
import datetime, sys

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

        # 1. 사용자 조회
        result = await db.execute(
            text("""
                SELECT user_email, user_password
                FROM users
                WHERE user_email = :user_email
                LIMIT 1
            """),
            {"user_email": user_id}
        )
        row = result.fetchone()
        if row is None:
            raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Incorrect username or password)")

        # 2. 비밀번호 검증
        db_password = row[1] if isinstance(row, (tuple, list)) else getattr(row, "user_password", None)
        if db_password is None or user_pw != db_password:
            raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Incorrect username or password)")

        # 3. 토큰 발급 (refresh_token 생성 로직은 engine 처리)
        response = await engine.post_user_login(db, user_id, user_pw)
        return response

    except HTTPException as ex:
        return await exception.handle_exception(ex, req, __file__)
    except Exception as ex:
        return await exception.handle_exception(ex, req, __file__)

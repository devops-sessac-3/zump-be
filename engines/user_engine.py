from fastapi import status, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from schemas import user_schema as schema
from queries import user_query as query
from utils.database import execute_post_async
from utils import messsage
from utils.config import config
from utils import exception, security
from utils.oauth import oauth


async def post_user_signup(db: AsyncSession, payload: schema.payload_user_signup):
    sql_query, parmas = query.post_user_signup(payload)
    
    await execute_post_async(db, sql_query, parmas)
    
    ret = Response(messsage.DATA_CREATE)
    ret.status_code = status.HTTP_201_CREATED
    
    return ret

    
async def post_user_login(db: AsyncSession, user_id: str, user_pw: str):
    # 1. 사용자 조회 (쿼리 모듈 사용)
    sql, params = query.get_user_by_email(user_id)
    result = await db.execute(text(sql), params)
    row = result.fetchone()
    if row is None:
        raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Incorrect username or password)")

    # 2. 비밀번호 검증 (동일성 비교 유지)
    db_password = row[1] if isinstance(row, (tuple, list)) else getattr(row, "user_password", None)
    if db_password is None or user_pw != db_password:
        raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Incorrect username or password)")

    # 3. 토큰 발급 (엔진에서 처리)
    security_user_pw: str = security.sha512Hash(user_pw)
    data = {
        "user_id": user_id,
        "user_pw": security_user_pw,
    }
    access_token = oauth.create_jwt_token(data)
    return schema.Token(**{"access_token": f"{access_token}"})

async def get(self, db: AsyncSession, config_name):
    try:
        account = await self.get_account(db)
        return [x for x in account if x.nick_nm == config_name] 
    except KeyError:
        return None

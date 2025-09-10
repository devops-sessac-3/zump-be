from fastapi import status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from schemas import user_schema as schema
from queries import user_query as query
from utils.database import execute_post_async
from utils import messsage
from utils.config import config

async def post_user_signup(db: AsyncSession, payload: schema.payload_user_signup):
    sql_query, parmas = query.post_user_signup(payload)
    
    await execute_post_async(db, sql_query, parmas)
    
    ret = Response(messsage.DATA_CREATE)
    ret.status_code = status.HTTP_201_CREATED
    
    return ret
    
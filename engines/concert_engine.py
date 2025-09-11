from fastapi import status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from schemas import concert_schema as schema
from queries import concert_query as query
from utils.database import execute_query_async
from utils.database import execute_post_async
# from utils.database import execute_post_multi_async
from utils import messsage
from utils import json_util


async def get_concerts(db: AsyncSession):
    sql_query, params = query.get_concerts()
    
    result_list = await execute_query_async(db, sql=sql_query, params=params, schema=schema.concert)
    return result_list

async def get_concert_detail(db: AsyncSession, concert_se: int):
    sql_query, params = query.get_concert_detail(concert_se)
    result_list = await execute_query_async(db, sql=sql_query, params=params, schema=schema.concert)
    if not result_list:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found (Concert not found)")
    return result_list[0]
    
async def post_concert_booking(db: AsyncSession, payload: schema.payload_concert_booking):
    sql_query, params = query.post_concert_booking(payload)
    
    await execute_post_async(db, sql=sql_query, params=params)
    ret = Response(messsage.DATA_CREATE)
    ret.status_code = status.HTTP_201_CREATED
    return ret
    
    

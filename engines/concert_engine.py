from sqlalchemy.ext.asyncio import AsyncSession
from schemas import concert_schema as schema
from queries import concert_query as query
from utils.database import execute_query_async


async def get_concerts(db: AsyncSession):
    sql_query, params = query.get_concerts()
    
    result_list = await execute_query_async(db, sql=sql_query, params=params, schema=schema.concert)
    return result_list

async def get_concert_detail(db: AsyncSession, concert_se: int):
    sql_query, params = query.get_concert_detail(concert_se)
    result_list = await execute_query_async(db, sql=sql_query, params=params, schema=schema.concert_detail)

    return result_list
    
async def post_concert_booking(db: AsyncSession, payload: schema.payload_concert_booking):
    sql_query, params = query.post_concert_booking(payload)
    
    result_list = await execute_query_async(db, sql=sql_query, params=params, schema=schema.concerts_seat)
    # ret = Response(messsage.DATA_CREATE)
    # ret.status_code = status.HTTP_201_CREATED
    return result_list
    
    

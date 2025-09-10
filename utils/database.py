from fastapi import HTTPException, status
from asyncpg import Connection as PgConnection
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from urllib.parse import quote_plus
from utils.config import config
from uuid import uuid4
from typing import Any, List
import re

class DatabaseBase:
    engine: any = None
    session_local: sessionmaker[Session] = None
    base: any = None
    debug_mode: bool = False
    
class CustomConnection(PgConnection):
    def _get_unique_id(self, prefix: str) -> str:
        return f'__asyncpg_{prefix}_{uuid4()}__'
    
class DatabaseAsync(DatabaseBase):
    """
    async await DB 연결 설정 공식문서 참고
    https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#prepared-statement-cache
    """
    def __init__(
        self,
        connection_string: str,
        debug_mode: bool,
        pool_size: int = 10,
        max_overflow: int = 10,
        idle_timeout: int = 30
    ):
        self.engine = create_async_engine(
            connection_string,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=idle_timeout,
            echo=debug_mode,
            connect_args={
                'server_settings': {
                    'application_name': 'zump-be-api',

                },
                'statement_cache_size': 0,
                'connection_class': CustomConnection,
            }
        )
        self.session_local = sessionmaker(
            bind=self.engine, 
            class_=AsyncSession,
        )

        self.base = declarative_base()
        
    async def __call__(self):
        async with self.session_local() as session:
            try:
                yield session
            finally:
                await session.close()

async def execute_query_async(db: AsyncSession, sql: str, params: dict[str, Any], schema: Any) -> List[Any]:
    """
    # Postgresql DB 전용 asyncpg 라이브러리에서 사용
    비동기 db sql을 실행하여 결과값을 스키마에 맞춰 반환하는 함수입니다.
    """
    try:
        query_result = await db.execute(text(sql), params=params)

        ret = []
        for row in query_result:
            obj = schema(**row._mapping)
            ret.append(obj)

        return ret
    except Exception as e:
        print(f"execute_query_async ERR: {e} {text(sql)} {params}")
        # 롤백
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

async def execute_post_async(db: AsyncSession, sql: str, params: dict[str, Any]) -> None:
    """
    비동기 쓰기성 SQL을 실행합니다. 트랜잭션은 컨텍스트에서 자동 커밋/롤백됩니다.
    """
    try:
        # 결과 반환        
        async with db.begin():  # 트랜잭션을 시작하고 자동으로 커밋 및 롤백 처리
            await db.execute(text(sql), params=params)


    except Exception as e:
        print(f"execute_post_async ERR: {e} {text(sql)} {params}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

debug_mode = config.get_config("DEBUG_MODE")


db_config = config.get_config("DATABASE_ZUMP")
db_url = "postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}".format(
    user=db_config["USERNAME"],
    password=quote_plus(db_config["PASSWORD"]),
    host=db_config["HOST"],
    port=db_config["PORT"],
    dbname=db_config["DB_NAME"],
    client_encoding=db_config["CLIENT_ENCODING"],
)
  
db_zump_async = DatabaseAsync(
    connection_string=db_url,
    debug_mode=debug_mode
)

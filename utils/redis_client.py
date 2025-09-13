"""
Redis 클라이언트 및 분산 락 구현
"""
import asyncio
import json
import time
import uuid
from typing import Optional, Any, Dict
import redis
from utils.config import config
from utils import exception
from fastapi import HTTPException, status


class RedisClient:
    """Redis 비동기 클라이언트"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.redis_config = config.get_config("REDIS")
        
    async def connect(self):
        """Redis 연결"""
        try:
            self.redis = redis.Redis(
                host=self.redis_config['HOST'],
                port=self.redis_config['PORT'],
                db=self.redis_config['DB'],
                password=self.redis_config.get('PASSWORD') or None,
                max_connections=self.redis_config['MAX_CONNECTIONS'],
                decode_responses=True
            )
            # 연결 테스트
            self.redis.ping()
            print("Redis 연결 성공")
        except Exception as e:
            print(f"Redis 연결 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redis 연결에 실패했습니다."
            )
    
    async def disconnect(self):
        """Redis 연결 해제"""
        if self.redis:
            self.redis.close()
    
    async def get(self, key: str) -> Optional[str]:
        """값 조회"""
        if not self.redis:
            await self.connect()
        return self.redis.get(key)
    
    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        """값 저장"""
        if not self.redis:
            await self.connect()
        return self.redis.set(key, value, ex=expire)
    
    async def delete(self, key: str) -> bool:
        """값 삭제"""
        if not self.redis:
            await self.connect()
        return self.redis.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        """키 존재 여부 확인"""
        if not self.redis:
            await self.connect()
        return self.redis.exists(key) > 0


class DistributedLock:
    """Redis 기반 분산 락"""
    
    def __init__(self, redis_client: RedisClient, lock_key: str, timeout: int = 10):
        self.redis = redis_client
        self.lock_key = f"lock:{lock_key}"
        self.timeout = timeout
        self.identifier = str(uuid.uuid4())
        self.acquired = False
    
    async def acquire(self) -> bool:
        """락 획득 시도"""
        if not self.redis.redis:
            await self.redis.connect()
        
        # SET 명령어로 원자적 락 획득 (NX: 키가 없을 때만 설정, EX: 만료시간 설정)
        result = self.redis.redis.set(
            self.lock_key, 
            self.identifier, 
            nx=True,  # 키가 존재하지 않을 때만 설정
            ex=self.timeout  # 만료시간 (초)
        )
        
        if result:
            self.acquired = True
            return True
        
        return False
    
    async def release(self) -> bool:
        """락 해제"""
        if not self.acquired:
            return False
        
        if not self.redis.redis:
            await self.redis.connect()
        
        # Lua 스크립트로 원자적 락 해제 (자신의 락인지 확인 후 삭제)
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        result = self.redis.redis.eval(lua_script, 1, self.lock_key, self.identifier)
        self.acquired = False
        return bool(result)
    
    async def extend(self, additional_time: int) -> bool:
        """락 시간 연장"""
        if not self.acquired:
            return False
        
        if not self.redis.redis:
            await self.redis.connect()
        
        # Lua 스크립트로 원자적 시간 연장
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("EXPIRE", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        result = self.redis.redis.eval(
            lua_script, 
            1, 
            self.lock_key, 
            self.identifier, 
            self.timeout + additional_time
        )
        return bool(result)
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        acquired = await self.acquire()
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="락 획득에 실패했습니다. 다른 사용자가 처리 중입니다."
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.release()


class CacheManager:
    """Redis 캐시 매니저"""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
    
    async def get_cached_data(self, key: str, data_type: str = "json") -> Optional[Any]:
        """캐시된 데이터 조회"""
        cached = await self.redis.get(key)
        if not cached:
            return None
        
        try:
            if data_type == "json":
                return json.loads(cached)
            return cached
        except (json.JSONDecodeError, TypeError):
            return None
    
    async def set_cached_data(self, key: str, data: Any, expire: int = 300) -> bool:
        """데이터 캐시 저장"""
        try:
            if isinstance(data, (dict, list)):
                value = json.dumps(data, ensure_ascii=False)
            else:
                value = str(data)
            
            return await self.redis.set(key, value, expire)
        except Exception as e:
            print(f"캐시 저장 실패: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """패턴에 맞는 캐시 삭제"""
        if not self.redis.redis:
            await self.redis.connect()
        
        keys = self.redis.redis.keys(pattern)
        if keys:
            return self.redis.redis.delete(*keys)
        return 0


# 전역 Redis 클라이언트 인스턴스
redis_client = RedisClient()
cache_manager = CacheManager(redis_client)

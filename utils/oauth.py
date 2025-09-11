import sys
from typing import Optional
from jose import JWTError
import jwt
from jwt import ExpiredSignatureError, InvalidSignatureError, PyJWTError
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import APIKeyHeader
from datetime import datetime, timedelta
from passlib.context import CryptContext
from utils import exception
from utils.config import config
from utils.database import db_zump_async

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

class Oauth():
    def __init__(self, ck_scope : str = ""):
        self.config = config.get_config("OAUTH")
        self.secret_key = self.config["JWT_SECRET_KEY"]
        self.algorithm = self.config["ALGORITHM"]
        self.expire = self.config["DEFAULT_JWT_EXPIRE_TIME"]
        
    async def __call__(self, Authorization: str = Depends(api_key_header), db: AsyncSession = Depends(db_zump_async)) -> dict:
        """
        (dependency) jwt 토큰의 유저정보와 만료시간이 유효한지 확인합니다.

        Exception:
            HTTPException: jwt 토큰의 만료시간과 유저정보가 유효하지 않을 때 발생
        """
        try:
            if config.get_config("OAUTH_TEST_CHECK")["TEST_CHECK"] : # 테스트모드 체크
                return 
            
            # 헤더 토큰 예외 처리
            if Authorization is None or "Basic" in Authorization:
                raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Token does not exist)")
            
            bearer, _, token = Authorization.partition(" ")
            if bearer != "bearer" and token == None:
                # 토큰이 형식에 맞지 않다면
                raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Token does not fit the format)")
            
            # jwt 복호화
            # decode 불가능 시 -> JWTError 발생
            # 토큰이 유효하지 않을 때 -> InvalidSignatureError 발생
            # 토큰이 expire 됐을 때 -> ExpiredSignatureError 발생
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            #sub = payload.get("sub")
            user_id: str = payload.get("user_id")
            user_pw: str = payload.get("user_pw")
            

            # 유저 이름이 없을 경우
            if user_id is None:
                raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED)
            
            # 유저 비번이 없을 경우
            if user_pw is None:
                raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED)
                            
            # 유효한 jwt일 경우
            payload["token"] = token
            # 토큰, username, expire 반환
            return payload

        except HTTPException as http_ex:
            raise http_ex
        except JWTError:
            raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED)
        except ExpiredSignatureError:
            raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Token has expired)")
        except InvalidSignatureError:
            raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized (Token is invalid)")
        except Exception:
            raise exception.get(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, ex=sys.exc_info())
    
    def create_jwt_token(self, data: dict, expire_minutes: int = None):
        """
        JWT 토큰을 생성합니다.

        Args:
            data (dict): jwt 토큰.
            expires_delta (timedelta): 만료 시간.

        Returns:
            response: jwt 토큰
        """
        to_encode = data.copy()
        if expire_minutes:
            expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.expire)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key , algorithm=self.algorithm )
        return encoded_jwt
    
    def decode_jwt_token(self, token: str):
        """
        JWT 토큰의 유효성을 검증합니다.

        Args:
            token (str): jwt 토큰.

        Returns:
            response: decode된 jwt 데이터.
        """
        try:
            payload = jwt.decode(token, self.secret_key , algorithms=[self.algorithm ])
            return payload
        except PyJWTError:
            raise exception.get(status_code=status.HTTP_401_UNAUTHORIZED)

oauth = Oauth()
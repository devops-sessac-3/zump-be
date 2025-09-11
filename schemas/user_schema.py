from pydantic import BaseModel, Field
from datetime import date
from typing import Annotated
from fastapi import Form
    
class payload_user_signup(BaseModel):
    user_email : str = Field(..., description="이메일")
    user_password : str = Field(..., description="비밀번호")
    user_name : str = Field(None, description="이름")
    class Config:
        from_attributes = True
    
class User:
    def __init__(
        self,
        *
        , user_id: Annotated[str, Form()] = ""
        , user_pw: Annotated[str, Form()] = ""
    ):
        self.user_id = user_id
        self.user_pw = user_pw    

class Refresh_token:
    def __init__(
        self,
        *
        , refresh_token: Annotated[str, Form()] = "암호화"
    ):
        self.refresh_token = refresh_token    

class Token(BaseModel):
    access_token: str = Field(..., description="access token")

# TokenPair 및 TokenResponse 스키마 정의
class TokenPair(BaseModel):
    access_token: str = Field(..., description="JWT 액세스 토큰")
    refresh_token: str = Field(..., description="암호화된 리프레시 토큰")

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT 액세스 토큰")
    refresh_token: str = Field(..., description="암호화된 리프레시 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
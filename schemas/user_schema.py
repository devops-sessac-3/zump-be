from pydantic import BaseModel, Field
from datetime import date
    
class payload_user_signup(BaseModel):
    user_email : str = Field(..., description="이메일")
    user_password : str = Field(..., description="비밀번호")
    class Config:
        from_attributes = True
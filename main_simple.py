#####################################################################
# ZUMP API Main (Simple Version)
# Redis, Kafka 없이 기본 기능만 테스트
# 실행 : uvicorn main_simple:app --reload 
# Swagger : http://127.0.0.1:8000/docs
# ReDoc : http://127.0.0.1:8000/redoc
#####################################################################

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

# 내부 모듈 import
from utils import exception
from utils.config import config
from routers import user_router    # 회원 관련 API 라우터 (예: /auth/signup)
from routers import concert_router # 공연 관련 API 라우터 (예: /concerts)

api_config = config.get_config("API_SETTING")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 함수"""
    # 시작 시
    print("ZUMP API 서버 시작")
    yield
    # 종료 시
    print("ZUMP API 서버 종료")

# FastAPI 앱 생성
app = FastAPI(
    title=api_config["TITLE"],
    description=api_config["DESCRIPTION"],
    version=api_config["VERSION"],
    lifespan=lifespan
)

# 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 환경에서는 특정 도메인만 허용 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(user_router.router)   # 회원가입/로그인 관련 API 라우터
app.include_router(concert_router.router)  # 공연 리스트/상세 API 라우터

# 글로벌 예외 처리
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    raise exception.get(status_code=422)

# 헬스 체크 엔드포인트
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "ZUMP API is running"}

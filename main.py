#####################################################################
# Zump API Main
# 실행 : uvicorn main:app --reload 
# Swagger : http://127.0.0.1:8080/docs
# ReDoc : http://127.0.0.1:8080/redoc
#####################################################################

import os
import sys

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

# 로컬 모듈이 전역 패키지보다 우선하도록 최상단에 삽입
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routers import concert_router  # 공연 관련 API 라우터 (예: /concerts)
from routers import healthcheck_router  # 헬스체크 API 라우터
from routers import queue_router
from routers import sse_router
from routers import user_router  # 회원 관련 API 라우터 (예: /auth/signup)
from services.queue_consumer import start_embedded_consumer, stop_embedded_consumer
from utils import exception
from utils.config import config

api_config = config.get_config("API_SETTING")

# FastAPI 앱 생성
app = FastAPI(
    title=api_config["TITLE"],
    description=api_config["DESCRIPTION"],
    version=api_config["VERSION"],
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
app.include_router(healthcheck_router.router)  # 헬스체크 API 라우터
app.include_router(queue_router.router)  # 대기열 enqueue API
app.include_router(sse_router.router)    # 대기열 SSE API

# 애플리케이션 라이프사이클 훅
@app.on_event("startup")
async def on_startup():
    print("애플리케이션 시작")
    # 내장 컨슈머 옵션 (API 프로세스 내 소비)
    if os.getenv("EMBEDDED_CONSUMER", "true").lower() in ("1", "true", "yes"): 
        start_embedded_consumer()


@app.on_event("shutdown")
async def on_shutdown():
    print("애플리케이션 종료")
    if os.getenv("EMBEDDED_CONSUMER", "true").lower() in ("1", "true", "yes"):
        await stop_embedded_consumer()

# 글로벌 예외 처리
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    raise exception.get(status_code=422)

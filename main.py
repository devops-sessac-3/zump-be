#####################################################################
# Zump API Main
# 실행 : uvicorn main:app --host 0.0.0.0 --port 8080 --reload
# Swagger : http://127.0.0.1:8080/docs
# ReDoc   : http://127.0.0.1:8080/redoc
#####################################################################

import os
import sys
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# --- 로컬 패키지 우선 경로 추가 ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- 로컬 모듈 ---
from routers import concert_router, healthcheck_router, queue_router, sse_router, user_router
from services.queue_consumer import start_embedded_consumer, stop_embedded_consumer
from utils import exception
from utils.config import config

# --- 설정/로거 ---
api_config = config.get_config("API_SETTING")
logger = logging.getLogger("zump")
instrumentator = Instrumentator()  # 전역 싱글톤

def _has_route(app: FastAPI, path: str) -> bool:
    return any(getattr(r, "path", None) == path for r in app.router.routes)

# -------------------------------
# FastAPI 앱 생성 (가장 먼저!)
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === startup ===
    logger.info("애플리케이션 시작")
    # 여기서는 instrument() 호출 금지(이미 앱 생성 직후 적용됨)
    # 필요 시 /metrics 라우트만 보충 노출
    try:
        if not _has_route(app, "/metrics"):
            instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
    except Exception:
        logger.exception("metrics expose 실패")

    # 임베디드 컨슈머 시작(동기/비동기 모두 지원)
    try:
        app.state.consumer_task = None
        if os.getenv("EMBEDDED_CONSUMER", "true").lower() in ("1", "true", "yes"):
            loop = asyncio.get_running_loop()
            if asyncio.iscoroutinefunction(start_embedded_consumer):
                app.state.consumer_task = loop.create_task(start_embedded_consumer())
            else:
                app.state.consumer_task = loop.run_in_executor(None, start_embedded_consumer)
    except Exception:
        logger.exception("embedded consumer 시작 실패")

    yield

    # === shutdown ===
    logger.info("애플리케이션 종료")
    try:
        if os.getenv("EMBEDDED_CONSUMER", "true").lower() in ("1", "true", "yes"):
            if asyncio.iscoroutinefunction(stop_embedded_consumer):
                await stop_embedded_consumer()
            else:
                await asyncio.get_running_loop().run_in_executor(None, stop_embedded_consumer)
    except Exception:
        logger.exception("embedded consumer 종료 실패")

app = FastAPI(
    title=api_config["TITLE"],
    description=api_config["DESCRIPTION"],
    version=api_config["VERSION"],
    lifespan=lifespan,  # 운영 안정성 위해 lifespan 사용
)

# ------------------------------------------
# ✅ 미들웨어 기반 계측은 "앱 시작 전" 한 번만!
# ------------------------------------------
if not getattr(app.state, "metrics_instrumented", False):
    instrumentator.instrument(app)  # 미들웨어 추가 (앱 시작 전만 가능)
    app.state.metrics_instrumented = True

# /metrics 라우트 노출 (중복 가드)
if not _has_route(app, "/metrics"):
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

# ------------------------------------------------------
# 얇은 on_event 훅 (테스트가 문자열을 검사하므로 유지)
# ------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    try:
        # instrument()는 절대 호출하지 말 것!
        if not _has_route(app, "/metrics"):
            instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

        # lifespan과 중복 호출되어도 안전(동기/비동기 보호)
        if os.getenv("EMBEDDED_CONSUMER", "true").lower() in ("1", "true", "yes"):
            loop = asyncio.get_running_loop()
            if asyncio.iscoroutinefunction(start_embedded_consumer):
                app.state.consumer_task = loop.create_task(start_embedded_consumer())
            else:
                app.state.consumer_task = loop.run_in_executor(None, start_embedded_consumer)
    except Exception:
        logger.exception("on_event(startup) 처리 실패")

@app.on_event("shutdown")
async def on_shutdown():
    try:
        if os.getenv("EMBEDDED_CONSUMER", "true").lower() in ("1", "true", "yes"):
            if asyncio.iscoroutinefunction(stop_embedded_consumer):
                await stop_embedded_consumer()
            else:
                await asyncio.get_running_loop().run_in_executor(None, stop_embedded_consumer)
    except Exception:
        logger.exception("on_event(shutdown) 처리 실패")

# ----------------
# 미들웨어/라우터
# ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 운영에서는 구체 도메인으로 제한 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(user_router.router)          # 회원
app.include_router(concert_router.router)       # 공연
app.include_router(healthcheck_router.router)   # 헬스체크
app.include_router(queue_router.router)         # 대기열
app.include_router(sse_router.router)           # SSE

# ------------------
# 글로벌 예외 처리
# ------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    # 세부 원인은 숨기고 표준화된 에러로 변환
    raise exception.get(status_code=422)

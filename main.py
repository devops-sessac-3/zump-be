# main.py
import os, sys, logging, asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routers import concert_router, healthcheck_router, queue_router, sse_router, user_router
from services.queue_consumer import start_embedded_consumer, stop_embedded_consumer
from utils import exception
from utils.config import config

api_config = config.get_config("API_SETTING")
logger = logging.getLogger("zump")

def _has_route(app: FastAPI, path: str) -> bool:
    return any(getattr(r, "path", None) == path for r in app.router.routes)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # === startup ===
    logger.info("애플리케이션 시작")
    # /metrics: 중복 등록 방지
    try:
        if not _has_route(app, "/metrics"):
            Instrumentator().instrument(app).expose(
                app,
                endpoint="/metrics",
                include_in_schema=False,
            )
    except Exception:
        logger.exception("metrics 초기화 실패")

    # 컨슈머: 블로킹이면 백그라운드로
    app.state.consumer_task = None
    if os.getenv("EMBEDDED_CONSUMER", "true").lower() in ("1", "true", "yes"):
        try:
            loop = asyncio.get_running_loop()
            # start_embedded_consumer가 동기라면 to_thread로, 코루틴이라면 create_task로
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
            # stop이 코루틴이면 await, 아니면 스레드에서 실행
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
    lifespan=lifespan,  # ✅ 여기로 이관
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,   # 운영 환경에선 구체 원본을 권장
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터
app.include_router(user_router.router)
app.include_router(concert_router.router)
app.include_router(healthcheck_router.router)
app.include_router(queue_router.router)
app.include_router(sse_router.router)

# 글로벌 예외 처리
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    raise exception.get(status_code=422)

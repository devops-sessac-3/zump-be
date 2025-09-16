#####################################################################
# Zump API Main
# 실행 : uvicorn main:app --reload 
# Swagger : http://127.0.0.1:8000/docs
# ReDoc : http://127.0.0.1:8000/redoc
#####################################################################

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

# 내부 모듈 import
from utils import exception
from utils.config import config
from routers import user_router    # 회원 관련 API 라우터 (예: /auth/signup)
from routers import concert_router # 공연 관련 API 라우터 (예: /concerts)
from routers import queue_router   # 대기열 관련 API 라우터
from routers import enqueue_router # 작업 큐 예시 라우터
from utils.kafka_client import event_manager
from utils.scheduler import default_scheduler
from utils.rank_subscriber import rank_subscriber

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
app.include_router(queue_router.router)    # 대기열 라우터
app.include_router(enqueue_router.router)  # 작업 큐 라우터

# 애플리케이션 라이프사이클 훅
@app.on_event("startup")
async def on_startup():
    try:
        # Kafka Producer 초기화 (소비는 필요시 개별 서비스에서 시작)
        await event_manager.initialize()
        print("✅ Kafka EventManager 초기화 성공")
    except Exception as e:
        print(f"⚠️  Kafka EventManager 초기화 실패 (계속 진행): {e}")
    
    try:
        # 대기열 스케줄러 시작
        await default_scheduler.start()
        print("✅ 대기열 스케줄러 시작 성공")
    except Exception as e:
        print(f"⚠️  대기열 스케줄러 시작 실패 (계속 진행): {e}")
    
    try:
        # 순번 갱신 구독자 시작 (Redis Pub/Sub -> SSE 브로드캐스트)
        await rank_subscriber.start()
        print("✅ 순번 갱신 구독자 시작 성공")
    except Exception as e:
        print(f"⚠️  순번 갱신 구독자 시작 실패 (계속 진행): {e}")


@app.on_event("shutdown")
async def on_shutdown():
    try:
        await default_scheduler.stop()
        print("✅ 대기열 스케줄러 정지 성공")
    except Exception as e:
        print(f"⚠️  대기열 스케줄러 정지 실패: {e}")
    
    try:
        await rank_subscriber.stop()
        print("✅ 순번 갱신 구독자 정지 성공")
    except Exception as e:
        print(f"⚠️  순번 갱신 구독자 정지 실패: {e}")
    
    try:
        await event_manager.shutdown()
        print("✅ Kafka EventManager 정지 성공")
    except Exception as e:
        print(f"⚠️  Kafka EventManager 정지 실패: {e}")

# 글로벌 예외 처리
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    raise exception.get(status_code=422)

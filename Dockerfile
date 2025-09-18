# zump-api 배포용 Dockerfile (FastAPI + Python 3.11.10)
FROM python:3.11.10-slim AS base

# 필수 패키지 설치 (빌드/런타임 모두 필요한 최소 패키지만 설치)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt만 먼저 복사 (레이어 캐싱 최적화)
COPY requirements.txt .

# 의존성 설치
RUN pip install --upgrade pip && pip install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# uvicorn 실행 포트
EXPOSE 8080

# 컨테이너 시작 시 실행할 명령어
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
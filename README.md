# Zump API Server

## 프로젝트 개요
공연 예매 서비스의 API를 담당하는 FastAPI 서버입니다.

## 프로젝트 
공연 예매 서비스의 api를 담당하는 서버입니다. 

## 파이썬 설치
```sh
# MAC
brew install python@3.11

# WINDOWS
winget install --id Python.Python.3.11 -e
```

## 가상환경 접속
```sh
python3.11 -m venv .venv
source .venv/bin/activate
```

## 패키지 라이브러리 설치
```sh
pip install -r requirements.txt
```

## 서버 배포 fastapi 실행
```sh
# 서버 배포 시
uvicorn main:app --host 0.0.0.0 --port 8080  
```

## 로컬 테스트 환경에서 실행
```sh
# kafka, zookeeper redis, postgres 컨테이너 실행
docker-compose up -d

APP_ENV=local uvicorn main:app --host 0.0.0.0 --port 8080
```
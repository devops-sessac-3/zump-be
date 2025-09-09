# sesacapi server

## 프로젝트 
공연 예매 서비스의 api를 담당하는 서버입니다. 

## 가상환경 접속
```sh
python -m venv .venv
source .venv/bin/active
```

## 패키지 라이브러리 설치
```sh
pip install -r requirements.txt
```

## fastapi 실행
```sh
uvicorn main:app --host 0.0.0.0 --port 8000  
```
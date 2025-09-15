"""
SSE 순번 갱신 데모 스크립트

- 특정 사용자(user_A)가 SSE로 자신의 순번/총원 이벤트를 실시간 수신
- 동시에 여러 사용자를 /queue/enter/{concert_se}로 투입해 변화 유도
- 스케줄러가 해당 concert_se를 처리해야 순번이 앞으로 당겨짐
  (기본 스케줄러는 concert_ids=["1","2","3","4","5"] 이므로, concert_se=1로 테스트 권장)

실행 예:
  python tests/sse_rank_demo.py            # 기본값 사용(concert=1, users=300)
  CONCERT_SE=1 USERS=500 CONCURRENCY=50 python tests/sse_rank_demo.py
"""
"""
SSE 순번 업데이트 데모 테스트

주요 기능:
- 다수 사용자를 대기열에 진입시켜 테스트 환경 구성
- 특정 사용자의 SSE 연결을 통해 실시간 순번 업데이트 확인
- 입장 완료 시 자동으로 대기열에서 제거하는 전체 생명주기 테스트
"""

import os
import json
import time
import requests
import concurrent.futures

# 환경 변수 설정
SERVER = os.getenv("SERVER", "http://127.0.0.1:8000")  # API 서버 주소
CONCERT_SE = os.getenv("CONCERT_SE", "1")  # 테스트할 공연 ID (스케줄러 기본 대상과 일치)
USER_A = os.getenv("USER_A", "1")  # SSE로 모니터링할 사용자 ID
USERS = int(os.getenv("USERS", "300"))  # 대기열에 진입시킬 사용자 수
CONCURRENCY = int(os.getenv("CONCURRENCY", "50"))  # 동시 요청 수


def enter(uid: str) -> int:
    """
    사용자를 대기열에 진입시킴
    
    Args:
        uid: 사용자 ID
        
    Returns:
        HTTP 상태 코드
    """
    url = f"{SERVER}/queue/enter/{CONCERT_SE}"
    try:
        r = requests.post(url, json={"user_id": uid}, timeout=5)
        return r.status_code
    except Exception:
        return 0


def leave_queue(uid: str) -> int:
    """
    사용자를 대기열에서 제거
    
    Args:
        uid: 사용자 ID
        
    Returns:
        HTTP 상태 코드
    """
    url = f"{SERVER}/queue/leave/{CONCERT_SE}"
    try:
        r = requests.post(url, json={"user_id": uid}, timeout=5)
        return r.status_code
    except Exception:
        return 0


def open_sse_and_print(uid: str, max_seconds: int = 20):
    """
    SSE 연결을 열고 실시간 순번 업데이트를 출력
    
    Args:
        uid: 사용자 ID
        max_seconds: 최대 연결 시간 (초)
    """
    url = f"{SERVER}/queue/sse"
    started = time.time()
    last_rank = None
    
    with requests.post(url, json={"user_id": uid}, stream=True, timeout=max_seconds+5) as resp:
        resp.raise_for_status()
        
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                if time.time() - started > max_seconds:
                    break
                continue
            if not line.startswith("data: "):
                continue
                
            data = line[len("data: "):]
            try:
                payload = json.loads(data)
            except Exception:
                print("[SSE RAW]", data)
                continue
                
            if isinstance(payload, dict) and payload.get("concert_se") == CONCERT_SE:
                current_rank = payload.get("rank")
                if current_rank != last_rank:  # 순번이 변경될 때만 출력
                    print("[SSE]", payload)
                    last_rank = current_rank
                
                # enter 이벤트를 받으면 대기열에서 제거하고 연결 종료
                if payload.get("type") == "enter":
                    print(f"[SSE] User {uid} entered! Leaving queue...")
                    leave_status = leave_queue(uid)
                    print(f"[LEAVE] Status: {leave_status}")
                    break
                    
            if time.time() - started > max_seconds:
                break


def main():
    """메인 테스트 함수"""
    print(f"SERVER={SERVER} CONCERT_SE={CONCERT_SE} USERS={USERS} CONCURRENCY={CONCURRENCY}")
    
    # 1) 먼저 다수 사용자 진입 (user_2, user_3, ...) - user_1보다 먼저
    print("bulk enter users first...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = [ex.submit(enter, f"user_{i}") for i in range(2, USERS + 2)]
        statuses = [f.result() for f in futures]
    print("ENTER 200 OK:", sum(1 for s in statuses if s == 200), "/", USERS)
    
    time.sleep(1)  # 다른 사용자들이 먼저 진입하도록 대기

    # 2) user_A(1) 진입 및 SSE 열기
    print(f"enter {USER_A} and open SSE...")
    enter(USER_A)

    # SSE 스트림 시작 (별도 스레드에서 실행)
    import threading
    t = threading.Thread(target=open_sse_and_print, args=(USER_A, 60), daemon=True)
    t.start()

    # 3) SSE 출력 대기 (스케줄러가 작동할 시간을 충분히 줌)
    t.join(timeout=60)
    print("done.")


if __name__ == "__main__":
    main()



"""
콘서트 대기열 부하 및 FIFO 검증 스크립트

기능:
- /queue/enter/{concert_se} 엔드포인트에 동시 요청 N개 전송
- 옵션: 샘플 사용자 1명의 SSE 스트림을 열고 상위 몇 개 이벤트를 콘솔에 출력
- 옵션: 일부 사용자 이탈 요청 전송
- FIFO 검증: 엔터 순서(user_0, user_1, ...)와 초기 rank(1, 2, ...)가 일치하는지 확인

환경 변수(없으면 기본값 사용):
- SERVER: 기본 http://127.0.0.1:8000
- CONCERT_SE: 기본 "123"
- USERS: 사용자 수(엔터 요청 개수), 기본 50 (상위 200 브로드캐스트 한계 고려)
- CONCURRENCY: 동시성, 기본 10
- DO_LEAVE: "1"이면 뒤에서 일부 사용자 이탈 테스트, 기본 0
- LEAVE_COUNT: 이탈 사용자 수, 기본 10
- SSE_USER: SSE를 열 사용자 아이디(예: user_0). 값이 있으면 SSE를 POST로 열어 10개 이벤트 출력
- VERIFY_FIRST_K: FIFO 검증 대상 사용자 수, 기본 20

실행 예:
  python tests/concert_queue_load_test.py
  CONCURRENCY=100 USERS=100 CONCERT_SE=456 VERIFY_FIRST_K=30 python tests/concert_queue_load_test.py
  SSE_USER=user_0 python tests/concert_queue_load_test.py
"""
import os
import sys
import time
import json
import requests
import concurrent.futures


SERVER = os.getenv("SERVER", "http://127.0.0.1:8000")
CONCERT_SE = os.getenv("CONCERT_SE", "123")
USERS = int(os.getenv("USERS", "50"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "10"))
DO_LEAVE = os.getenv("DO_LEAVE", "0") == "1"
LEAVE_COUNT = int(os.getenv("LEAVE_COUNT", "10"))
SSE_USER = os.getenv("SSE_USER")
VERIFY_FIRST_K = int(os.getenv("VERIFY_FIRST_K", "20"))


def enter(idx: int) -> int:
    user_id = f"user_{idx}"
    url = f"{SERVER}/queue/enter/{CONCERT_SE}"
    try:
        r = requests.post(url, json={"user_id": user_id}, timeout=5)
        return r.status_code
    except Exception:
        return 0


def leave(idx: int) -> int:
    user_id = f"user_{idx}"
    url = f"{SERVER}/queue/leave/{CONCERT_SE}"
    try:
        r = requests.post(url, json={"user_id": user_id}, timeout=5)
        return r.status_code
    except Exception:
        return 0


def open_sse(user_id: str, max_events: int = 10, timeout_sec: int = 30):
    """SSE 스트림을 열고 일부 이벤트를 콘솔에 출력"""
    url = f"{SERVER}/queue/sse"
    try:
        with requests.post(url, json={"user_id": user_id}, stream=True, timeout=timeout_sec) as resp:
            resp.raise_for_status()
            printed = 0
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[len("data: "):]
                    try:
                        payload = json.loads(data)
                    except Exception:
                        payload = data
                    print("[SSE]", payload)
                    printed += 1
                    if printed >= max_events:
                        break
    except Exception as e:
        print("[SSE_ERROR]", e)


def main():
    print(f"SERVER={SERVER} CONCERT_SE={CONCERT_SE} USERS={USERS} CONCURRENCY={CONCURRENCY} VERIFY_FIRST_K={VERIFY_FIRST_K}")

    # 옵션: SSE 미리 열기
    if SSE_USER:
        print(f"Opening SSE for user_id={SSE_USER} (async preview)")
        # 간단히 백그라운드처럼 먼저 몇 개 이벤트만 출력
        try:
            open_sse(SSE_USER, max_events=10, timeout_sec=30)
        except Exception as e:
            print("SSE open failed:", e)

    # 엔터 부하 (user_0..user_{USERS-1} 순으로 전송)
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = [ex.submit(enter, i) for i in range(USERS)]
        statuses = [f.result() for f in futures]
    elapsed = time.time() - start
    ok = sum(1 for s in statuses if s == 200)
    print(f"ENTER -> 200 OK: {ok}/{USERS}, time={elapsed:.2f}s")

    # 워커/브로드캐스트 반영 대기 (짧게)
    time.sleep(0.5)

    # FIFO 검증: 상위 K 사용자(user_0..user_{K-1})의 초기 rank가 1..K 인지 확인
    K = min(VERIFY_FIRST_K, USERS)
    print(f"Verifying FIFO for first {K} users...")
    failures = []
    for i in range(K):
        uid = f"user_{i}"
        try:
            # SSE 1회 부트스트랩 랭크만 수신
            url = f"{SERVER}/queue/sse"
            with requests.post(url, json={"user_id": uid}, stream=True, timeout=10) as resp:
                resp.raise_for_status()
                got_rank = None
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    try:
                        payload = json.loads(data)
                    except Exception:
                        continue
                    if isinstance(payload, dict) and payload.get("type") == "rank" and payload.get("concert_se") == CONCERT_SE:
                        got_rank = int(payload.get("rank", 0))
                        print(f"[VERIFY] {uid} -> rank={got_rank}")
                        break
                # 연결을 더 유지할 필요 없음 → 종료
            expected = i + 1
            if got_rank != expected:
                failures.append((uid, expected, got_rank))
        except Exception as e:
            failures.append((uid, i + 1, f"error:{e}"))

    if failures:
        print("FIFO check FAILED for:")
        for uid, exp, got in failures:
            print(f" - {uid}: expected {exp}, got {got}")
    else:
        print("FIFO check PASSED for first", K)

    # 옵션: 이탈 테스트
    if DO_LEAVE:
        leave_targets = min(LEAVE_COUNT, USERS)
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
            futures = [ex.submit(leave, i) for i in range(leave_targets)]
            statuses = [f.result() for f in futures]
        elapsed = time.time() - start
        ok = sum(1 for s in statuses if s == 200)
        print(f"LEAVE -> 200 OK: {ok}/{leave_targets}, time={elapsed:.2f}s")


if __name__ == "__main__":
    main()



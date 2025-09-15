"""
간단 부하 테스트: 100개의 병렬 요청으로 /enqueue 호출하여 Kafka 프로듀서/워커 라인 검증
실행 방법:
  1) 서버 실행: uvicorn main:app --host 0.0.0.0 --port 8000
  2) 워커 실행: python workers/worker.py
  3) 이 스크립트 실행: python tests/kafka_queue_test.py
"""
import concurrent.futures
import requests
import time


SERVER = "http://127.0.0.1:8000"
THREADS = 100


def enqueue(i: int) -> str:
    payload = {"concert_se": "123", "user_se": f"user_{i}"}
    r = requests.post(f"{SERVER}/enqueue", json=payload, timeout=5)
    r.raise_for_status()
    return r.json()["task_id"]


def get_status(task_id: str) -> str:
    # 간단 폴링: 최대 5초
    for _ in range(10):
        r = requests.get(f"{SERVER}/enqueue/task/{task_id}", timeout=3)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "completed":
            return "completed"
        time.sleep(0.5)
    return "timeout"


def main():
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        futures = [ex.submit(enqueue, i) for i in range(THREADS)]
        task_ids = [f.result() for f in futures]

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        futures = [ex.submit(get_status, tid) for tid in task_ids]
        results = [f.result() for f in futures]

    ok = sum(1 for s in results if s == "completed")
    print(f"Completed: {ok}/{THREADS} in {time.time()-start:.2f}s")


if __name__ == "__main__":
    main()



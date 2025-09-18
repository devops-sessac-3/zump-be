import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import redis


API_BASE = os.getenv("SERVER", "http://localhost:8080")
CONCERT_SE = os.getenv("CONCERT_SE", "1")
ME_USER_SE = int(os.getenv("USER_A", "300"))
TOTAL_USERS = int(os.getenv("USERS", "300"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "50"))
DEQUEUE_PER_SEC = int(os.getenv("DEQUEUE_PER_SEC", "10"))  # 초당 제거 인원


def enqueue_user(user_se: int) -> bool:
    try:
        r = requests.post(
            f"{API_BASE}/queue/enqueue",
            json={"concert_se": CONCERT_SE, "user_se": user_se},
            timeout=5,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False


def enqueue_users(total: int) -> None:
    ok = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = [ex.submit(enqueue_user, i) for i in range(1, total + 1)]
        for f in as_completed(futures):
            if f.result():
                ok += 1
    print(f"[enqueue] sent={total} ok={ok}")


def fetch_status(user_se: int) -> tuple[int, int]:
    try:
        resp = requests.get(
            f"{API_BASE}/queue/status",
            params={"concert_se": CONCERT_SE, "user_se": user_se},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return int(data.get("rank", -1)), int(data.get("total", 0))
    except Exception:
        pass
    return -1, 0


def sse_watch_stop_event(stop_evt: threading.Event) -> None:
    url = f"{API_BASE}/queue/stream?concert_se={CONCERT_SE}&user_se={ME_USER_SE}"
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if stop_evt.is_set():
                break
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            try:
                payload = json.loads(data)
            except Exception:
                print(f"[sse raw] {data}")
                continue
            print(
                f"[sse] rank={payload.get('rank')} total={payload.get('total')} ts={payload.get('ts')}"
            )


def processor_loop_stop_event(stop_evt: threading.Event) -> None:
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    zkey = f"q:zset:{CONCERT_SE}"
    chn = f"q:chn:{CONCERT_SE}"
    while not stop_evt.is_set():
        removed = r.zpopmin(zkey, DEQUEUE_PER_SEC)
        if removed:
            r.publish(chn, "update")
        time.sleep(1)


def main() -> None:
    # 초기화
    rcli = redis.Redis(host="localhost", port=6379, decode_responses=True)
    rcli.delete(f"q:zset:{CONCERT_SE}")

    # 1) 대량 등록
    enqueue_users(TOTAL_USERS)

    # 2) 큐 진입 확인 후 시작
    print("[wait] waiting until ME is in queue...")
    while True:
        rank, total = fetch_status(ME_USER_SE)
        if rank != -1:
            print(f"[status] entered queue rank={rank} total={total}")
            break
        time.sleep(0.2)

    # 3) SSE 구독 및 프로세서 시작
    stop_evt = threading.Event()
    sse_t = threading.Thread(target=sse_watch_stop_event, args=(stop_evt,), daemon=True)
    proc_t = threading.Thread(target=processor_loop_stop_event, args=(stop_evt,), daemon=True)
    sse_t.start()
    proc_t.start()

    # 4) 이탈까지 모니터링
    try:
        while True:
            rank, _ = fetch_status(ME_USER_SE)
            if rank == -1:
                print("[done] left the queue")
                break
            time.sleep(1)
    finally:
        stop_evt.set()
        sse_t.join(timeout=2)
        proc_t.join(timeout=2)


if __name__ == "__main__":
    main()



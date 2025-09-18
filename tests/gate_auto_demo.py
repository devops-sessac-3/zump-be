"""
대기열 게이트(auto) 테스트 스크립트 - API만 사용

시나리오:
1) /queue/enqueue로 100명 투입 → AUTO_QUEUE_SIZE_THRESHOLD=100을 충족
2) user_A가 상세조회 호출 → 425(QUEUE_WAIT) 기대
3) /queue/stream으로 순번 구독 + /queue/status로 확인
4) 선두가 되면 상세조회 재호출 → 200 기대

환경변수:
- SERVER: API 주소 (기본 http://localhost:8080)
- CONCERT_SE: 테스트 콘서트 ID (기본 1)
- USERS: 초기 투입 인원(기본 100)
- USER_A: 모니터링할 사용자(기본 105)
"""

import os
import sys
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


SERVER = os.getenv("SERVER", "http://localhost:8080")
CONCERT_SE = os.getenv("CONCERT_SE", "1")
USERS = int(os.getenv("USERS", "100"))
USER_A = int(os.getenv("USER_A", "105"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "50"))


def enqueue(user_se: int) -> bool:
    try:
        r = requests.post(
            f"{SERVER}/queue/enqueue",
            json={"concert_se": CONCERT_SE, "user_se": user_se},
            timeout=5,
        )
        return r.status_code in (200, 202)
    except Exception:
        return False


def enqueue_bulk(n: int) -> None:
    ok = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = [ex.submit(enqueue, i) for i in range(1, n + 1)]
        for f in as_completed(futures):
            ok += 1 if f.result() else 0
    print(f"[enqueue] sent={n} ok={ok}")


def get_detail(user_se: int) -> requests.Response:
    return requests.get(
        f"{SERVER}/concerts/{CONCERT_SE}", params={"user_se": user_se}, timeout=5
    )


def get_status(user_se: int) -> tuple[int, int]:
    try:
        r = requests.get(
            f"{SERVER}/queue/status",
            params={"concert_se": CONCERT_SE, "user_se": user_se},
            timeout=5,
        )
        if r.status_code == 200:
            d = r.json()
            return int(d.get("rank", -1)), int(d.get("total", 0))
    except Exception:
        pass
    return -1, 0


def sse_watch(user_se: int, stop_evt: threading.Event) -> None:
    url = f"{SERVER}/queue/stream?concert_se={CONCERT_SE}&user_se={user_se}"
    try:
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
                    continue
                print(
                    f"[sse] rank={payload.get('rank')} total={payload.get('total')} ts={payload.get('ts')}"
                )
    except Exception as e:
        print("[sse] closed:", e)


def main() -> None:
    enqueue_bulk(USERS)

    resp = get_detail(USER_A)
    body = None
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:200]}

    if resp.status_code not in (200, 202, 425):
        print(f"[detail] unexpected status={resp.status_code} body={body}")
        return

    if resp.status_code == 200:
        print("[detail] gate inactive; detail fetched immediately")
        print("[detail-result]", body)
        return

    print("[wait] waiting until ME is in queue...")
    rank, total = get_status(USER_A)
    while rank <= 0:
        time.sleep(0.2)
        rank, total = get_status(USER_A)
    print(f"[status] entered queue rank={rank} total={total}")

    stop_evt = threading.Event()
    t = threading.Thread(target=sse_watch, args=(USER_A, stop_evt), daemon=True)
    t.start()

    # 폴링으로 선두 여부 확인 (또는 퇴장 감지)
    while True:
        rank, total = get_status(USER_A)
        if rank == 1:
            break
        if rank == -1:
            print("[status] admitted; queue slot consumed")
            break
        time.sleep(0.5)

    stop_evt.set()
    t.join(timeout=2)

    resp2 = get_detail(USER_A)
    try:
        print("[detail-final]", resp2.status_code, resp2.json())
    except Exception:
        print("[detail-final]", resp2.status_code, resp2.text[:200])

    # SSE 스트림 누적 출력 여유
    time.sleep(0.2)


if __name__ == "__main__":
    main()

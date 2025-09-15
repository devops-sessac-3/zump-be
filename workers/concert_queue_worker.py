"""
공연 대기열 전용 Kafka 워커

주요 기능:
- concert_queue 토픽에서 대기열 이벤트를 소비
- 사용자 진입/이탈 이벤트 처리
- Redis Pub/Sub을 통한 순번 업데이트 트리거
- 동시 처리를 위한 ThreadPoolExecutor 사용
"""

from confluent_kafka import Consumer
from redis import Redis
import json
import os
import time
import concurrent.futures
from utils.redis_client import RedisQueue

# Kafka Consumer 설정
kafka_config = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "concert_queue_group",  # 워커 그룹 ID
    "auto.offset.reset": "earliest"  # 오프셋 리셋 정책
}

consumer = Consumer(kafka_config)
consumer.subscribe(["concert_queue"])  # concert_queue 토픽 구독

# Redis 클라이언트 초기화
redis_client = Redis(host="localhost", port=6379, decode_responses=True)
queue = None

# 동시성 및 지연 설정 (환경 변수에서 읽기)
WORKER_CONCURRENCY = int(os.getenv("CONCERT_WORKER_CONCURRENCY", "8"))  # 동시 처리 스레드 수
CONCERT_DELAY_MS = int(os.getenv("CONCERT_DELAY_MS", "0"))  # 메시지 처리 지연 시간 (ms)


def ensure_queue():
    """RedisQueue 객체 초기화 (지연 로딩)"""
    global queue
    if queue is None:
        # utils.redis_client.RedisQueue는 asyncio 기반이지만 이 워커는 동기 실행이므로
        # 동기 Redis 클라이언트를 받아도 대부분의 명령은 동일 키로 동작합니다.
        # 필요시 별도 동기 버전 유틸로 분리 가능
        queue = RedisQueue(redis_client)  # type: ignore


def handle_message(message: dict):
    """
    Kafka 메시지 처리 함수
    
    Args:
        message: 처리할 메시지 딕셔너리 (action, concert_se, user_id 포함)
    """
    ensure_queue()
    action = message.get("action")  # enter 또는 leave
    concert_se = message.get("concert_se")  # 공연 식별자
    user_id = message.get("user_id")  # 사용자 ID
    
    if not concert_se or not user_id:
        return

    # RedisQueue는 async 메서드로 정의되어 있으므로, 동기 워커에서 단순히 Redis 명령을 직접 호출합니다.
    if action == "enter":
        # API에서 이미 ZSET/SEQ 등록 완료. 워커는 브로드캐스트만 트리거
        # 순번 갱신 요청을 Pub/Sub 채널로 발행(서버가 구독 후 SSE 브로드캐스트)
        redis_client.publish("queue:rank_request", concert_se)
        print(f"[CONCERT_WORKER] User {user_id} entered queue for concert {concert_se}. Publishing rank update request.")
    elif action == "leave":
        # 사용자를 ZSet에서 제거하고 메타데이터 삭제
        redis_client.zrem(f"queue:concert:{concert_se}", user_id)
        redis_client.delete(f"queue:user:{user_id}:meta")
        redis_client.publish("queue:rank_request", concert_se)
        print(f"[CONCERT_WORKER] User {user_id} left queue for concert {concert_se}. Publishing rank update request.")
    
    # 처리 지연 (성능 테스트용)
    if CONCERT_DELAY_MS > 0:
        time.sleep(CONCERT_DELAY_MS / 1000.0)


def main():
    """워커 메인 함수"""
    print(f"concert_queue worker running... concurrency={WORKER_CONCURRENCY}, delay_ms={CONCERT_DELAY_MS}")
    try:
        while True:
            # 배치로 메시지 소비 (성능 최적화)
            msgs = consumer.consume(num_messages=WORKER_CONCURRENCY * 2, timeout=1.0)
            if not msgs:
                continue
                
            # 메시지 파싱 및 검증
            tasks: list[dict] = []
            for msg in msgs:
                if msg is None or msg.error():
                    if msg is not None and msg.error():
                        print(f"[ERROR] {msg.error()}")
                    continue
                try:
                    tasks.append(json.loads(msg.value().decode("utf-8")))
                except Exception as e:
                    print(f"[PARSE_ERROR] {e}")
                    
            if not tasks:
                continue
                
            # ThreadPoolExecutor를 사용하여 동시 처리 (성능 최적화)
            with concurrent.futures.ThreadPoolExecutor(max_workers=WORKER_CONCURRENCY) as executor:
                futures = [executor.submit(handle_message, t) for t in tasks]
                for f in concurrent.futures.as_completed(futures):
                    _ = f.result()  # 예외 발생 시 여기서 처리
                    
    except KeyboardInterrupt:
        print("worker stopped")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()



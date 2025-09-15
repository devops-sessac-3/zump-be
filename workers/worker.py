from confluent_kafka import Consumer
from redis import Redis
import json
import time
import os
import concurrent.futures


# Kafka Consumer 설정
kafka_config = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "worker_group",
    "auto.offset.reset": "earliest"
}
consumer = Consumer(kafka_config)

# Redis 클라이언트 초기화
redis_client = Redis(host="localhost", port=6379, decode_responses=True)

# 동시성 및 처리 지연 설정 (환경변수로 조정 가능)
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "16"))
TASK_PROCESSING_MS = int(os.getenv("TASK_PROCESSING_MS", "0"))

# Kafka 토픽 구독
consumer.subscribe(["task_topic"])


def process_task(task_data: dict):
    task_id = task_data["id"]

    # 작업 상태 업데이트: processing
    task_data["status"] = "processing"
    redis_client.set(task_id, json.dumps(task_data))

    print(f"[PROCESSING] Task {task_id}: concert={task_data.get('concert_se')}, user={task_data.get('user_se')}")
    if TASK_PROCESSING_MS > 0:
        time.sleep(TASK_PROCESSING_MS / 1000.0)

    # 작업 상태 업데이트: completed
    task_data["status"] = "completed"
    redis_client.set(task_id, json.dumps(task_data))
    print(f"[DONE] Task {task_id} completed.")


def main():
    print(f"Worker running... concurrency={WORKER_CONCURRENCY}, processing_ms={TASK_PROCESSING_MS}")
    try:
        while True:
            msgs = consumer.consume(num_messages=WORKER_CONCURRENCY * 2, timeout=1.0)
            if not msgs:
                continue
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
            with concurrent.futures.ThreadPoolExecutor(max_workers=WORKER_CONCURRENCY) as executor:
                futures = [executor.submit(process_task, t) for t in tasks]
                for f in concurrent.futures.as_completed(futures):
                    _ = f.result()
    except KeyboardInterrupt:
        print("Worker stopped.")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()



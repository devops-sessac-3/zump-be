from fastapi import APIRouter, BackgroundTasks
import uuid
import json
from confluent_kafka import Producer
from redis import Redis
from pydantic import BaseModel

router = APIRouter(prefix="/enqueue", tags=["enqueue"]) 

# Kafka Producer 설정
kafka_config = {
    "bootstrap.servers": "localhost:9092"
}
producer = Producer(kafka_config)

# Redis 클라이언트 초기화 (상태 조회/업데이트용)
redis_client = Redis(host="localhost", port=6379, decode_responses=True)


class EnqueuePayload(BaseModel):
    concert_se: str
    user_se: str


@router.post("")
async def enqueue_task(payload: EnqueuePayload, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())  # 난수 UUID 사용
    task_data = {"id": task_id, "concert_se": payload.concert_se, "user_se": payload.user_se, "status": "queued"}

    # Kafka로 메시지 전송
    producer.produce("task_topic", key=task_id, value=json.dumps(task_data))
    producer.flush()

    return {"message": "Task enqueued", "task_id": task_id}


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    task_data = redis_client.get(task_id)
    if task_data:
        task = json.loads(task_data)
        # 작업 상태를 'completed'로 업데이트 (예시)
        task["status"] = "completed"
        redis_client.set(task["id"], json.dumps(task))
        # 완료 후 삭제 (예시)
        redis_client.delete(task["id"])
        return {"task_id": task["id"], "status": task["status"]}
    return {"message": "Task not found", "task_id": task_id}

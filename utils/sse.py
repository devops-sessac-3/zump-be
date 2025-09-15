import asyncio
import json
from typing import AsyncGenerator, Dict


class SSEManager:
    """사용자별 SSE 연결 관리"""

    def __init__(self):
        self.user_queues: Dict[str, asyncio.Queue] = {}

    async def connect(self, user_id: str) -> AsyncGenerator[bytes, None]:
        queue = self.user_queues.setdefault(user_id, asyncio.Queue(maxsize=1000))
        try:
            # 초기 핑
            await queue.put({"type": "connected"})
            while True:
                data = await queue.get()
                payload = f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
                yield payload
        finally:
            # 연결 종료 시 큐 정리
            self.user_queues.pop(user_id, None)

    async def send(self, user_id: str, event: Dict):
        queue = self.user_queues.get(user_id)
        if queue:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # 과도한 이벤트는 드롭
                pass

    async def broadcast(self, user_ids: list[str], event: Dict):
        for uid in user_ids:
            await self.send(uid, event)


sse_manager = SSEManager()



from __future__ import annotations

import asyncio
from typing import Optional

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from utils.config import config


class AsyncKafka:
    """aiokafka 기반 Kafka Producer/Consumer 관리.

    Lazy-start로 필요 시 시작. FastAPI 수명주기 혹은 워커에서 사용.
    """

    _producer: Optional[AIOKafkaProducer] = None

    def __init__(self) -> None:
        self._cfg = config.get_config("KAFKA")
        self._bootstrap = self._cfg["BOOTSTRAP_SERVERS"]
        self._client_id = self._cfg.get("CLIENT_ID", "zump-api")
        self._loop = asyncio.get_event_loop()

    async def start_producer(self) -> None:
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                loop=self._loop,
                bootstrap_servers=self._bootstrap,
                acks=self._cfg.get("ACKS", "all"),
                client_id=self._client_id,
                linger_ms=5,
                value_serializer=lambda v: v.encode("utf-8"),
            )
            await self._producer.start()

    async def stop_producer(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def send(self, topic: str, value: str, key: Optional[str] = None, timeout_sec: float = 5.0) -> None:
        await self.start_producer()
        try:
            await asyncio.wait_for(
                self._producer.send_and_wait(
                    topic,
                    value=value,
                    key=(key.encode("utf-8") if key else None),
                ),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError(f"Kafka send timeout after {timeout_sec}s") from exc


kafka_async = AsyncKafka()



from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional, Tuple

from aiokafka import AIOKafkaConsumer

from utils.config import config
from utils.redis_client import redis_client


_consumer_task: Optional[asyncio.Task] = None


def _parse_message(value: bytes) -> Tuple[str, str]:
    raw = value.decode("utf-8")
    concert_se, user_se = raw.split("|", 1)
    return concert_se, user_se


async def _consume_loop() -> None:
    logging.basicConfig(level=logging.INFO, format="[embedded-consumer] %(asctime)s %(levelname)s: %(message)s")

    kafka_cfg = config.get_config("KAFKA")
    topic = kafka_cfg["QUEUE_TOPIC"]
    bootstrap = kafka_cfg["BOOTSTRAP_SERVERS"]

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        group_id="concert-projector",
        value_deserializer=lambda v: v,
    )

    r = redis_client.redis
    
    async def dequeue_loop() -> None:
        """옵션: 초당 N명씩 처리(임베디드 모드 전용)."""
        # 우선순위: ENV > config.local > config
        queue_cfg = config.get_config("QUEUE") or {}
        per_sec = int(os.getenv("CONCERT_DEQUEUE_PER_SEC", str(queue_cfg.get("DEQUEUE_PER_SEC", 0))))
        ready_ttl = int(os.getenv("QUEUE_GATE_READY_TTL_SEC", str(queue_cfg.get("AUTO_GATE_STATE_TTL_SEC", 30))))
        if ready_ttl <= 0:
            ready_ttl = 30
        if per_sec <= 0:
            return
        logging.info(f"[embedded-consumer] Dequeue loop enabled: {per_sec}/sec")
        while True:
            try:
                keys = [k async for k in r.scan_iter(match="q:zset:*", count=50)]
                for zkey in keys:
                    removed = await r.zpopmin(zkey, per_sec)
                    if removed:
                        concert_se = zkey.split(":")[-1]
                        for member, _score in removed:
                            gate_key = f"q:gate:{concert_se}:{member}"
                            await r.setex(gate_key, ready_ttl, "ready")
                        await r.publish(f"q:chn:{concert_se}", "update")
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logging.exception(f"[embedded-consumer] Dequeue loop error: {e}")
                await asyncio.sleep(1)
    logging.info(f"Starting embedded consumer on {bootstrap}, topic={topic}")
    await consumer.start()
    try:
        dq_task: Optional[asyncio.Task] = None
        if int(os.getenv("CONCERT_DEQUEUE_PER_SEC", str(config.get_config("QUEUE").get("DEQUEUE_PER_SEC", 0)))) > 0:
            dq_task = asyncio.create_task(dequeue_loop())
        async for msg in consumer:
            try:
                concert_se, user_se = _parse_message(msg.value)
                zkey = f"q:zset:{concert_se}"
                # FIFO 안정성: 파티션 내 단조 증가하는 offset을 점수로 사용
                score = msg.offset
                added = await r.zadd(zkey, {str(user_se): score})
                await r.publish(f"q:chn:{concert_se}", "update")
                logging.info(
                    f"Consumed offset={msg.offset} -> ZADD {zkey} {user_se} {score} (added={added})"
                )
            except Exception as e:
                logging.exception(f"Failed processing message: {e}")
    except asyncio.CancelledError:
        logging.info("Embedded consumer cancelled")
        raise
    finally:
        # stop dequeue loop
        tasks = []
        for t in [locals().get('dq_task')]:
            if isinstance(t, asyncio.Task) and not t.done():
                t.cancel()
                tasks.append(t)
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        await consumer.stop()


def start_embedded_consumer() -> None:
    global _consumer_task
    if _consumer_task is None or _consumer_task.done():
        _consumer_task = asyncio.create_task(_consume_loop())


async def stop_embedded_consumer() -> None:
    global _consumer_task
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None

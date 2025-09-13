"""
Kafka 이벤트 브로커 클라이언트
Python 3.13.7 호환성 문제 해결을 위한 Kafka 클라이언트
"""
import asyncio
import json
import logging
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError
from utils.config import config
from fastapi import HTTPException, status

# 로거 설정
logger = logging.getLogger(__name__)

class EventTypes(Enum):
    """이벤트 타입 정의"""
    SEAT_BOOKED = "seat_booked"
    SEAT_CANCELLED = "seat_cancelled"
    CONCERT_CREATED = "concert_created"
    CONCERT_UPDATED = "concert_updated"
    USER_REGISTERED = "user_registered"
    BOOKING_CREATED = "booking_created"
    BOOKING_CANCELLED = "booking_cancelled"

class KafkaEventProducer:
    """Kafka 이벤트 프로듀서"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.kafka_config = config.get_config("KAFKA")
        self.bootstrap_servers = self.kafka_config["BOOTSTRAP_SERVERS"]
    
    async def connect(self):
        """Kafka 프로듀서 연결"""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # 모든 복제본에 쓰기 확인
                request_timeout_ms=30000
            )
            await self.producer.start()
            logger.info("Kafka Producer 연결 성공")
        except Exception as e:
            logger.error(f"Kafka Producer 연결 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Kafka Producer 연결에 실패했습니다."
            )
    
    async def disconnect(self):
        """Kafka 프로듀서 연결 해제"""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer 연결 해제")
    
    async def send_event(self, topic: str, event: Dict[str, Any], key: Optional[str] = None) -> bool:
        """이벤트 발행"""
        if not self.producer:
            await self.connect()
        
        try:
            # 이벤트에 메타데이터 추가
            event_with_metadata = {
                **event,
                "timestamp": asyncio.get_event_loop().time(),
                "event_id": f"{topic}_{asyncio.get_event_loop().time()}"
            }
            
            await self.producer.send_and_wait(
                topic=topic,
                value=event_with_metadata,
                key=key
            )
            logger.info(f"이벤트 발행 성공: {topic} - {event_with_metadata.get('event_type', 'unknown')}")
            return True
        except KafkaError as e:
            logger.error(f"이벤트 발행 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"이벤트 발행 중 예외 발생: {e}")
            return False


class KafkaEventConsumer:
    """Kafka 이벤트 컨슈머"""
    
    def __init__(self, group_id: str = None):
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.kafka_config = config.get_config("KAFKA")
        self.bootstrap_servers = self.kafka_config["BOOTSTRAP_SERVERS"]
        self.group_id = group_id or self.kafka_config["GROUP_ID"]
        self.auto_offset_reset = self.kafka_config["AUTO_OFFSET_RESET"]
        self.running = False
    
    async def connect(self, topics: List[str]):
        """Kafka 컨슈머 연결"""
        try:
            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
                max_poll_records=100
            )
            await self.consumer.start()
            logger.info(f"Kafka Consumer 연결 성공: {topics}")
        except Exception as e:
            logger.error(f"Kafka Consumer 연결 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Kafka Consumer 연결에 실패했습니다."
            )
    
    async def disconnect(self):
        """Kafka 컨슈머 연결 해제"""
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka Consumer 연결 해제")
    
    async def consume_events(self, event_handler: Callable[[Dict[str, Any]], None]):
        """이벤트 소비"""
        if not self.consumer:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Kafka Consumer가 연결되지 않았습니다."
            )
        
        self.running = True
        logger.info("이벤트 소비 시작")
        
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                try:
                    event_data = message.value
                    logger.info(f"이벤트 수신: {message.topic} - {event_data.get('event_type', 'unknown')}")
                    await event_handler(event_data)
                except Exception as e:
                    logger.error(f"이벤트 처리 중 오류 발생: {e}")
                    continue
        except Exception as e:
            logger.error(f"이벤트 소비 중 오류 발생: {e}")
        finally:
            logger.info("이벤트 소비 종료")
    
    async def stop(self):
        """이벤트 소비 중지"""
        self.running = False


class KafkaEventManager:
    """Kafka 이벤트 매니저 (프로듀서 + 컨슈머)"""
    
    def __init__(self):
        self.producer = KafkaEventProducer()
        self.consumer: Optional[KafkaEventConsumer] = None
        self.consumer_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """이벤트 매니저 초기화"""
        try:
            await self.producer.connect()
            logger.info("Kafka EventManager 초기화 완료")
        except Exception as e:
            logger.error(f"Kafka EventManager 초기화 실패: {e}")
            raise
    
    async def shutdown(self):
        """이벤트 매니저 종료"""
        try:
            if self.consumer_task:
                self.consumer_task.cancel()
                try:
                    await self.consumer_task
                except asyncio.CancelledError:
                    pass
            
            if self.consumer:
                await self.consumer.disconnect()
            
            await self.producer.disconnect()
            logger.info("Kafka EventManager 종료 완료")
        except Exception as e:
            logger.error(f"Kafka EventManager 종료 중 오류: {e}")
    
    async def publish_event(self, event_type: EventTypes, data: Dict[str, Any], topic: str = "zump_events", key: Optional[str] = None) -> bool:
        """이벤트 발행"""
        event = {
            "event_type": event_type.value,
            "data": data
        }
        return await self.producer.send_event(topic, event, key)
    
    async def consume_events(self, topics: List[str], event_handler: Callable[[Dict[str, Any]], None], group_id: str = None):
        """이벤트 소비 시작"""
        try:
            self.consumer = KafkaEventConsumer(group_id)
            await self.consumer.connect(topics)
            
            # 백그라운드에서 이벤트 소비 시작
            self.consumer_task = asyncio.create_task(
                self.consumer.consume_events(event_handler)
            )
            logger.info(f"이벤트 소비 시작: {topics}")
        except Exception as e:
            logger.error(f"이벤트 소비 시작 실패: {e}")
            raise
    
    async def stop_consuming(self):
        """이벤트 소비 중지"""
        if self.consumer:
            await self.consumer.stop()
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass


# 전역 이벤트 매니저 인스턴스
event_manager = KafkaEventManager()

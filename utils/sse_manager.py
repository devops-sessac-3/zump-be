"""
SSE (Server Sent Event) 매니저
실시간 좌석 상태 업데이트를 위한 SSE 관리
"""
import asyncio
import json
import time
from typing import Dict, Set, Any, Optional
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from utils.kafka_client import event_manager, EventTypes
import logging

logger = logging.getLogger(__name__)


class SSEClient:
    """SSE 클라이언트 연결 관리"""
    
    def __init__(self, client_id: str, concert_se: int = None, seat_number: int = None):
        self.client_id = client_id
        self.concert_se = concert_se
        self.seat_number = seat_number
        self.queue = asyncio.Queue()
        self.connected = True
        self.last_heartbeat = time.time()
    
    async def send_event(self, event_data: Dict[str, Any]):
        """클라이언트에게 이벤트 전송"""
        if self.connected:
            try:
                await self.queue.put(event_data)
            except Exception as e:
                logger.error(f"이벤트 전송 실패: {e}")
                self.connected = False
    
    async def disconnect(self):
        """클라이언트 연결 해제"""
        self.connected = False
        try:
            await self.queue.put(None)  # 종료 신호
        except:
            pass
    
    def is_interested_in_event(self, event_data: Dict[str, Any]) -> bool:
        """이벤트에 관심이 있는지 확인"""
        if not self.connected:
            return False
        
        event_type = event_data.get("event_type")
        event_concert_se = event_data.get("concert_se")
        event_seat_number = event_data.get("seat_number")
        
        # 모든 좌석 이벤트에 관심
        if self.concert_se is None:
            return event_type in [EventTypes.SEAT_BOOKED, EventTypes.SEAT_CANCELLED, EventTypes.SEAT_STATE_CHANGED]
        
        # 특정 공연의 좌석 이벤트에 관심
        if self.concert_se == event_concert_se:
            if self.seat_number is None:
                return event_type in [EventTypes.SEAT_BOOKED, EventTypes.SEAT_CANCELLED, EventTypes.SEAT_STATE_CHANGED]
            else:
                return (event_type in [EventTypes.SEAT_BOOKED, EventTypes.SEAT_CANCELLED, EventTypes.SEAT_STATE_CHANGED] 
                        and event_seat_number == self.seat_number)
        
        return False


class SSEManager:
    """SSE 연결 관리자"""
    
    def __init__(self):
        self.clients: Dict[str, SSEClient] = {}
        self.concert_subscriptions: Dict[int, Set[str]] = {}  # concert_se -> client_ids
        self.seat_subscriptions: Dict[str, Set[str]] = {}  # "concert_se:seat_number" -> client_ids
        self.running = False
    
    async def add_client(self, client_id: str, concert_se: int = None, seat_number: int = None) -> SSEClient:
        """SSE 클라이언트 추가"""
        client = SSEClient(client_id, concert_se, seat_number)
        self.clients[client_id] = client
        
        # 구독 관리
        if concert_se is not None:
            if concert_se not in self.concert_subscriptions:
                self.concert_subscriptions[concert_se] = set()
            self.concert_subscriptions[concert_se].add(client_id)
            
            if seat_number is not None:
                seat_key = f"{concert_se}:{seat_number}"
                if seat_key not in self.seat_subscriptions:
                    self.seat_subscriptions[seat_key] = set()
                self.seat_subscriptions[seat_key].add(client_id)
        
        logger.info(f"SSE 클라이언트 추가: {client_id} (concert_se: {concert_se}, seat_number: {seat_number})")
        return client
    
    async def remove_client(self, client_id: str):
        """SSE 클라이언트 제거"""
        if client_id in self.clients:
            client = self.clients[client_id]
            await client.disconnect()
            
            # 구독 정리
            if client.concert_se is not None:
                if client.concert_se in self.concert_subscriptions:
                    self.concert_subscriptions[client.concert_se].discard(client_id)
                    if not self.concert_subscriptions[client.concert_se]:
                        del self.concert_subscriptions[client.concert_se]
                
                if client.seat_number is not None:
                    seat_key = f"{client.concert_se}:{client.seat_number}"
                    if seat_key in self.seat_subscriptions:
                        self.seat_subscriptions[seat_key].discard(client_id)
                        if not self.seat_subscriptions[seat_key]:
                            del self.seat_subscriptions[seat_key]
            
            del self.clients[client_id]
            logger.info(f"SSE 클라이언트 제거: {client_id}")
    
    async def broadcast_event(self, event_data: Dict[str, Any]):
        """이벤트를 구독자들에게 브로드캐스트"""
        event_type = event_data.get("event_type")
        concert_se = event_data.get("concert_se")
        seat_number = event_data.get("seat_number")
        
        # 이벤트에 관심이 있는 클라이언트들 찾기
        target_clients = set()
        
        # 전체 좌석 이벤트 구독자
        for client_id, client in self.clients.items():
            if client.is_interested_in_event(event_data):
                target_clients.add(client_id)
        
        # 특정 공연 구독자
        if concert_se in self.concert_subscriptions:
            target_clients.update(self.concert_subscriptions[concert_se])
        
        # 특정 좌석 구독자
        if seat_number is not None:
            seat_key = f"{concert_se}:{seat_number}"
            if seat_key in self.seat_subscriptions:
                target_clients.update(self.seat_subscriptions[seat_key])
        
        # 이벤트 전송
        for client_id in target_clients:
            if client_id in self.clients:
                await self.clients[client_id].send_event(event_data)
    
    async def get_client_count(self) -> int:
        """연결된 클라이언트 수 반환"""
        return len(self.clients)
    
    async def get_concert_subscribers(self, concert_se: int) -> int:
        """특정 공연 구독자 수 반환"""
        return len(self.concert_subscriptions.get(concert_se, set()))
    
    async def get_seat_subscribers(self, concert_se: int, seat_number: int) -> int:
        """특정 좌석 구독자 수 반환"""
        seat_key = f"{concert_se}:{seat_number}"
        return len(self.seat_subscriptions.get(seat_key, set()))


class SSEStreamer:
    """SSE 스트림 생성기"""
    
    def __init__(self, sse_manager: SSEManager):
        self.sse_manager = sse_manager
    
    async def create_stream(self, client_id: str, concert_se: int = None, seat_number: int = None):
        """SSE 스트림 생성"""
        client = await self.sse_manager.add_client(client_id, concert_se, seat_number)
        
        async def event_generator():
            try:
                # 연결 확인 메시지
                yield f"data: {json.dumps({'type': 'connected', 'client_id': client_id, 'timestamp': time.time()}, ensure_ascii=False)}\n\n"
                
                # 하트비트 및 이벤트 처리
                while client.connected:
                    try:
                        # 큐에서 이벤트 대기 (타임아웃 30초)
                        event_data = await asyncio.wait_for(client.queue.get(), timeout=30.0)
                        
                        if event_data is None:  # 종료 신호
                            break
                        
                        # SSE 형식으로 이벤트 전송
                        sse_data = f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                        yield sse_data
                        
                    except asyncio.TimeoutError:
                        # 하트비트 전송
                        heartbeat = {
                            "type": "heartbeat",
                            "timestamp": time.time(),
                            "client_id": client_id
                        }
                        yield f"data: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"
                        
                    except Exception as e:
                        logger.error(f"SSE 스트림 오류: {e}")
                        break
                
            except Exception as e:
                logger.error(f"SSE 스트림 생성 오류: {e}")
            finally:
                # 클라이언트 정리
                await self.sse_manager.remove_client(client_id)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )


class SSEEventProcessor:
    """SSE 이벤트 프로세서"""
    
    def __init__(self, sse_manager: SSEManager):
        self.sse_manager = sse_manager
        self.running = False
    
    async def start(self):
        """이벤트 프로세서 시작"""
        self.running = True
        
        # Kafka 이벤트 구독
        await event_manager.consume_events(
            topics=["seat_events"],
            event_handler=self._handle_seat_event
        )
        
        logger.info("SSE 이벤트 프로세서 시작")
    
    async def stop(self):
        """이벤트 프로세서 중지"""
        self.running = False
        await event_manager.stop_consuming()
        logger.info("SSE 이벤트 프로세서 중지")
    
    async def _handle_seat_event(self, event_data: Dict[str, Any]):
        """좌석 이벤트 처리"""
        try:
            # SSE 클라이언트들에게 이벤트 브로드캐스트
            await self.sse_manager.broadcast_event(event_data)
            logger.info(f"좌석 이벤트 처리 완료: {event_data.get('event_type')}")
            
        except Exception as e:
            logger.error(f"좌석 이벤트 처리 실패: {e}")


# 전역 SSE 매니저 인스턴스
sse_manager = SSEManager()
sse_streamer = SSEStreamer(sse_manager)
sse_event_processor = SSEEventProcessor(sse_manager)

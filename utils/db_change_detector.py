# """
# 데이터베이스 변경 감지 유틸리티
# PostgreSQL의 LISTEN/NOTIFY를 사용한 실시간 DB 변경 감지
# """
# import asyncio
# import json
# import logging
# from typing import Dict, Any, Optional, Callable
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import text
# from utils.kafka_client import event_manager, EventTypes
# from utils.redis_client import cache_manager
# import asyncpg

# logger = logging.getLogger(__name__)


# class DatabaseChangeDetector:
#     """데이터베이스 변경 감지기"""
    
#     def __init__(self):
#         self.connection: Optional[asyncpg.Connection] = None
#         self.running = False
#         self.change_handlers: Dict[str, Callable] = {}
#         self.db_config = None
    
#     async def initialize(self, db_config: Dict[str, Any]):
#         """변경 감지기 초기화"""
#         self.db_config = db_config
        
#         # PostgreSQL 연결
#         connection_string = f"postgresql://{db_config['USERNAME']}:{db_config['PASSWORD']}@{db_config['HOST']}:{db_config['PORT']}/{db_config['DB_NAME']}"
        
#         try:
#             self.connection = await asyncpg.connect(connection_string)
#             logger.info("데이터베이스 변경 감지기 연결 성공")
#         except Exception as e:
#             logger.error(f"데이터베이스 변경 감지기 연결 실패: {e}")
#             raise
    
#     async def start_listening(self):
#         """변경 감지 시작"""
#         if not self.connection:
#             raise Exception("데이터베이스 연결이 없습니다.")
        
#         self.running = True
        
#         # PostgreSQL 채널 구독
#         await self.connection.add_listener('db_changes', self._handle_notification)
        
#         # 변경 감지 루프 시작
#         asyncio.create_task(self._listen_loop())
        
#         logger.info("데이터베이스 변경 감지 시작")
    
#     async def stop_listening(self):
#         """변경 감지 중지"""
#         self.running = False
        
#         if self.connection:
#             await self.connection.remove_listener('db_changes', self._handle_notification)
#             await self.connection.close()
#             self.connection = None
        
#         logger.info("데이터베이스 변경 감지 중지")
    
#     async def _listen_loop(self):
#         """변경 감지 루프"""
#         try:
#             while self.running:
#                 await asyncio.sleep(1)  # 1초마다 체크
#         except Exception as e:
#             logger.error(f"변경 감지 루프 오류: {e}")
    
#     async def _handle_notification(self, connection, pid, channel, payload):
#         """PostgreSQL NOTIFY 이벤트 처리"""
#         try:
#             # JSON 페이로드 파싱
#             change_data = json.loads(payload)
            
#             table_name = change_data.get('table')
#             operation = change_data.get('operation')
            
#             logger.info(f"DB 변경 감지: {table_name}.{operation}")
            
#             # 테이블별 처리
#             if table_name == 'concerts_seat':
#                 await self._handle_seat_change(change_data)
#             elif table_name == 'concert_booking':
#                 await self._handle_booking_change(change_data)
#             elif table_name == 'concerts':
#                 await self._handle_concert_change(change_data)
#             elif table_name == 'users':
#                 await self._handle_user_change(change_data)
            
#         except Exception as e:
#             logger.error(f"변경 이벤트 처리 실패: {e}")
    
#     async def _handle_seat_change(self, change_data: Dict[str, Any]):
#         """좌석 테이블 변경 처리"""
#         operation = change_data.get('operation')
#         old_data = change_data.get('old_data', {})
#         new_data = change_data.get('new_data', {})
        
#         concert_se = new_data.get('concert_se') or old_data.get('concert_se')
#         seat_number = new_data.get('seat_number') or old_data.get('seat_number')
#         is_booked = new_data.get('is_booked')
        
#         if not concert_se or not seat_number:
#             return
        
#         # 캐시 무효화
#         await self._invalidate_seat_cache(concert_se, seat_number)
        
#         # 이벤트 발행
#         event_data = {
#             "event_type": EventTypes.SEAT_STATE_CHANGED,
#             "concert_se": concert_se,
#             "seat_number": seat_number,
#             "is_booked": is_booked,
#             "operation": operation,
#             "timestamp": asyncio.get_event_loop().time()
#         }
        
#         await event_manager.publish_event(
#             topic="seat_events",
#             event=event_data,
#             key=f"{concert_se}:{seat_number}"
#         )
        
#         logger.info(f"좌석 상태 변경 이벤트 발행: {concert_se}:{seat_number}")
    
#     async def _handle_booking_change(self, change_data: Dict[str, Any]):
#         """예매 테이블 변경 처리"""
#         operation = change_data.get('operation')
#         old_data = change_data.get('old_data', {})
#         new_data = change_data.get('new_data', {})
        
#         concert_se = new_data.get('concert_se') or old_data.get('concert_se')
#         seat_number = new_data.get('seat_number') or old_data.get('seat_number')
#         user_se = new_data.get('user_se') or old_data.get('user_se')
#         booking_se = new_data.get('booking_se') or old_data.get('booking_se')
        
#         if not concert_se or not seat_number:
#             return
        
#         # 캐시 무효화
#         await self._invalidate_seat_cache(concert_se, seat_number)
        
#         # 이벤트 타입 결정
#         if operation == 'INSERT':
#             event_type = EventTypes.SEAT_BOOKED
#         elif operation == 'DELETE':
#             event_type = EventTypes.SEAT_CANCELLED
#         else:
#             event_type = EventTypes.SEAT_STATE_CHANGED
        
#         # 이벤트 발행
#         event_data = {
#             "event_type": event_type,
#             "concert_se": concert_se,
#             "seat_number": seat_number,
#             "user_se": user_se,
#             "booking_se": booking_se,
#             "operation": operation,
#             "timestamp": asyncio.get_event_loop().time()
#         }
        
#         await event_manager.publish_event(
#             topic="seat_events",
#             event=event_data,
#             key=f"{concert_se}:{seat_number}"
#         )
        
#         logger.info(f"예매 변경 이벤트 발행: {event_type} - {concert_se}:{seat_number}")
    
#     async def _handle_concert_change(self, change_data: Dict[str, Any]):
#         """공연 테이블 변경 처리"""
#         operation = change_data.get('operation')
#         new_data = change_data.get('new_data', {})
#         old_data = change_data.get('old_data', {})
        
#         concert_se = new_data.get('concert_se') or old_data.get('concert_se')
        
#         if not concert_se:
#             return
        
#         # 공연 관련 캐시 무효화
#         await cache_manager.invalidate_pattern("concerts:*")
#         await cache_manager.invalidate_pattern(f"seat_state:concert:{concert_se}")
        
#         # 이벤트 타입 결정
#         if operation == 'INSERT':
#             event_type = EventTypes.CONCERT_CREATED
#         elif operation == 'UPDATE':
#             event_type = EventTypes.CONCERT_UPDATED
#         else:
#             return
        
#         # 이벤트 발행
#         event_data = {
#             "event_type": event_type,
#             "concert_se": concert_se,
#             "operation": operation,
#             "concert_data": new_data,
#             "timestamp": asyncio.get_event_loop().time()
#         }
        
#         await event_manager.publish_event(
#             topic="concert_events",
#             event=event_data,
#             key=str(concert_se)
#         )
        
#         logger.info(f"공연 변경 이벤트 발행: {event_type} - {concert_se}")
    
#     async def _handle_user_change(self, change_data: Dict[str, Any]):
#         """사용자 테이블 변경 처리"""
#         operation = change_data.get('operation')
#         new_data = change_data.get('new_data', {})
        
#         user_se = new_data.get('user_se')
        
#         if not user_se:
#             return
        
#         # 이벤트 타입 결정
#         if operation == 'INSERT':
#             event_type = EventTypes.USER_REGISTERED
#         else:
#             return
        
#         # 이벤트 발행
#         event_data = {
#             "event_type": event_type,
#             "user_se": user_se,
#             "operation": operation,
#             "user_data": new_data,
#             "timestamp": asyncio.get_event_loop().time()
#         }
        
#         await event_manager.publish_event(
#             topic="user_events",
#             event=event_data,
#             key=str(user_se)
#         )
        
#         logger.info(f"사용자 변경 이벤트 발행: {event_type} - {user_se}")
    
#     async def _invalidate_seat_cache(self, concert_se: int, seat_number: int):
#         """좌석 관련 캐시 무효화"""
#         # 특정 좌석 캐시 삭제
#         seat_cache_key = f"seat_state:{concert_se}:{seat_number}"
#         await cache_manager.redis.delete(seat_cache_key)
        
#         # 공연 전체 좌석 캐시 삭제
#         concert_cache_key = f"seat_state:concert:{concert_se}"
#         await cache_manager.redis.delete(concert_cache_key)
    
#     def add_change_handler(self, table_name: str, handler: Callable):
#         """변경 핸들러 추가"""
#         self.change_handlers[table_name] = handler
#         logger.info(f"변경 핸들러 추가: {table_name}")


# class DatabaseTriggerManager:
#     """데이터베이스 트리거 관리자"""
    
#     def __init__(self, db_config: Dict[str, Any]):
#         self.db_config = db_config
    
#     async def create_change_triggers(self):
#         """변경 감지 트리거 생성"""
#         connection_string = f"postgresql://{self.db_config['USERNAME']}:{self.db_config['PASSWORD']}@{self.db_config['HOST']}:{self.db_config['PORT']}/{self.db_config['DB_NAME']}"
        
#         try:
#             conn = await asyncpg.connect(connection_string)
            
#             # 트리거 함수 생성
#             await conn.execute("""
#                 CREATE OR REPLACE FUNCTION notify_db_changes()
#                 RETURNS TRIGGER AS $$
#                 DECLARE
#                     payload JSON;
#                 BEGIN
#                     payload = json_build_object(
#                         'table', TG_TABLE_NAME,
#                         'operation', TG_OP,
#                         'old_data', CASE WHEN TG_OP = 'DELETE' THEN row_to_json(OLD) ELSE NULL END,
#                         'new_data', CASE WHEN TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN row_to_json(NEW) ELSE NULL END
#                     );
                    
#                     PERFORM pg_notify('db_changes', payload::text);
#                     RETURN COALESCE(NEW, OLD);
#                 END;
#                 $$ LANGUAGE plpgsql;
#             """)
            
#             # 좌석 테이블 트리거
#             await conn.execute("""
#                 DROP TRIGGER IF EXISTS concerts_seat_change_trigger ON concerts_seat;
#                 CREATE TRIGGER concerts_seat_change_trigger
#                     AFTER INSERT OR UPDATE OR DELETE ON concerts_seat
#                     FOR EACH ROW EXECUTE FUNCTION notify_db_changes();
#             """)
            
#             # 예매 테이블 트리거
#             await conn.execute("""
#                 DROP TRIGGER IF EXISTS concert_booking_change_trigger ON concert_booking;
#                 CREATE TRIGGER concert_booking_change_trigger
#                     AFTER INSERT OR UPDATE OR DELETE ON concert_booking
#                     FOR EACH ROW EXECUTE FUNCTION notify_db_changes();
#             """)
            
#             # 공연 테이블 트리거
#             await conn.execute("""
#                 DROP TRIGGER IF EXISTS concerts_change_trigger ON concerts;
#                 CREATE TRIGGER concerts_change_trigger
#                     AFTER INSERT OR UPDATE OR DELETE ON concerts
#                     FOR EACH ROW EXECUTE FUNCTION notify_db_changes();
#             """)
            
#             # 사용자 테이블 트리거
#             await conn.execute("""
#                 DROP TRIGGER IF EXISTS users_change_trigger ON users;
#                 CREATE TRIGGER users_change_trigger
#                     AFTER INSERT OR UPDATE OR DELETE ON users
#                     FOR EACH ROW EXECUTE FUNCTION notify_db_changes();
#             """)
            
#             await conn.close()
#             logger.info("데이터베이스 변경 감지 트리거 생성 완료")
            
#         except Exception as e:
#             logger.error(f"트리거 생성 실패: {e}")
#             raise
    
#     async def drop_change_triggers(self):
#         """변경 감지 트리거 삭제"""
#         connection_string = f"postgresql://{self.db_config['USERNAME']}:{self.db_config['PASSWORD']}@{self.db_config['HOST']}:{self.db_config['PORT']}/{self.db_config['DB_NAME']}"
        
#         try:
#             conn = await asyncpg.connect(connection_string)
            
#             # 트리거 삭제
#             await conn.execute("DROP TRIGGER IF EXISTS concerts_seat_change_trigger ON concerts_seat;")
#             await conn.execute("DROP TRIGGER IF EXISTS concert_booking_change_trigger ON concert_booking;")
#             await conn.execute("DROP TRIGGER IF EXISTS concerts_change_trigger ON concerts;")
#             await conn.execute("DROP TRIGGER IF EXISTS users_change_trigger ON users;")
            
#             # 함수 삭제
#             await conn.execute("DROP FUNCTION IF EXISTS notify_db_changes();")
            
#             await conn.close()
#             logger.info("데이터베이스 변경 감지 트리거 삭제 완료")
            
#         except Exception as e:
#             logger.error(f"트리거 삭제 실패: {e}")


# # 전역 변경 감지기 인스턴스
# db_change_detector = DatabaseChangeDetector()

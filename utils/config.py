#####################################################################
# Config 모듈
#####################################################################

import json
import os

# config 파일 경로 세팅
config_path = 'configs/config.json'

class Config():
    def __init__(self) -> None:
        with open(config_path, 'r', encoding='UTF8') as f:
            self.config = json.load(f)

    def get_config(self, config_name):
        try:
            config_data = self.config[config_name]
            
            # 환경 변수로 오버라이드
            if config_name == "KAFKA":
                if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
                    config_data["BOOTSTRAP_SERVERS"] = [os.getenv("KAFKA_BOOTSTRAP_SERVERS")]
            elif config_name == "DATABASE_ZUMP":
                if os.getenv("DATABASE_HOST"):
                    config_data["HOST"] = os.getenv("DATABASE_HOST")
                if os.getenv("REDIS_HOST"):
                    # Redis 설정이 별도로 있다면 여기에 추가
                    pass
                    
            return config_data
        except KeyError:
            return None
    
config = Config()

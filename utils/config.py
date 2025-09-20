#####################################################################
# Config 모듈
#####################################################################

import json
import os

# config 파일 경로 세팅
config_path = 'configs/config.json'
local_config_path = 'configs/config.local.json'

class Config():
    def __init__(self) -> None:
        with open(config_path, 'r', encoding='UTF8') as f:
            base = json.load(f)

        # 로컬 오버레이(config.local.json) 존재 시, APP_ENV=local 에서만 머지
        if os.getenv("APP_ENV") == "local" and os.path.exists(local_config_path):
            try:
                with open(local_config_path, 'r', encoding='UTF8') as lf:
                    local_cfg = json.load(lf)
                base = self._deep_merge(base, local_cfg)
            except Exception:
                pass

        self.config = base

    def _deep_merge(self, base: dict, overlay: dict) -> dict:
        for k, v in overlay.items():
            if (
                k in base and isinstance(base[k], dict) and isinstance(v, dict)
            ):
                base[k] = self._deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    def get_config(self, config_name):
        try:
            config_data = self.config[config_name]
            
            # 환경 변수로 오버라이드
            if config_name == "DATABASE_ZUMP":
                if os.getenv("DATABASE_HOST"):
                    config_data["HOST"] = os.getenv("DATABASE_HOST")
            if config_name == "REDIS":
                if os.getenv("REDIS_HOST"):
                    config_data["HOST"] = os.getenv("REDIS_HOST")
                if os.getenv("REDIS_PORT"):
                    config_data["PORT"] = int(os.getenv("REDIS_PORT"))
                if os.getenv("REDIS_DB"):
                    config_data["DB"] = int(os.getenv("REDIS_DB"))
                if os.getenv("REDIS__PASSWORD"):
                    config_data["PASSWORD"] = os.getenv("REDIS__PASSWORD")
            if config_name == "KAFKA":
                if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
                    config_data["BOOTSTRAP_SERVERS"] = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
                if os.getenv("KAFKA_QUEUE_TOPIC"):
                    config_data["QUEUE_TOPIC"] = os.getenv("KAFKA_QUEUE_TOPIC")
                if os.getenv("KAFKA_CLIENT_ID"):
                    config_data["CLIENT_ID"] = os.getenv("KAFKA_CLIENT_ID")
                    
            return config_data
        except KeyError:
            return None
    
config = Config()

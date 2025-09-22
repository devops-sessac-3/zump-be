#####################################################################
# Config 모듈 (보강 버전)
#####################################################################

import json
import os
import copy

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
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                base[k] = self._deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    def _get_int(self, env_key: str):
        """환경변수 값을 int로 안전 변환. 미설정/변환불가면 None."""
        val = os.getenv(env_key)
        if val is None or val == "":
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def _get_bool(self, env_key: str):
        """환경변수 불리언 파싱: true/1/yes/on → True, false/0/no/off → False"""
        val = os.getenv(env_key)
        if val is None:
            return None
        s = val.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        if s in ("false", "0", "no", "off"):
            return False
        return None

    def get_config(self, config_name):
        try:
            # 변이 방지: 내부 원본 보호
            config_data = copy.deepcopy(self.config[config_name])

            # === 공통: DEBUG_MODE 같은 단일 스칼라도 env로 오버라이드할 수 있게 ===
            if config_name == "DEBUG_MODE":
                b = self._get_bool("DEBUG_MODE")
                if b is not None:
                    return b
                return config_data

            # === DB ===
            if config_name == "DATABASE_ZUMP":
                if os.getenv("DATABASE_HOST"):
                    config_data["HOST"] = os.getenv("DATABASE_HOST")
                port = self._get_int("DATABASE_PORT")
                if port is not None:
                    config_data["PORT"] = port
                rport = self._get_int("DATABASE_READ_PORT")
                if rport is not None:
                    config_data["READ_PORT"] = rport
                if os.getenv("DATABASE_DB_NAME"):
                    config_data["DB_NAME"] = os.getenv("DATABASE_DB_NAME")
                if os.getenv("DATABASE_USERNAME"):
                    config_data["USERNAME"] = os.getenv("DATABASE_USERNAME")
                if os.getenv("DATABASE_PASSWORD"):
                    config_data["PASSWORD"] = os.getenv("DATABASE_PASSWORD")
                if os.getenv("DATABASE_CLIENT_ENCODING") is not None:
                    config_data["CLIENT_ENCODING"] = os.getenv("DATABASE_CLIENT_ENCODING")

            # === REDIS ===
            if config_name == "REDIS":
                if os.getenv("REDIS_HOST"):
                    config_data["HOST"] = os.getenv("REDIS_HOST")
                port = self._get_int("REDIS_PORT")
                if port is not None:
                    config_data["PORT"] = port
                db = self._get_int("REDIS_DB")
                if db is not None:
                    config_data["DB"] = db
                if os.getenv("REDIS_PASSWORD"):
                    config_data["PASSWORD"] = os.getenv("REDIS_PASSWORD")

            # === KAFKA ===
            if config_name == "KAFKA":
                if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
                    config_data["BOOTSTRAP_SERVERS"] = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
                if os.getenv("KAFKA_QUEUE_TOPIC"):
                    config_data["QUEUE_TOPIC"] = os.getenv("KAFKA_QUEUE_TOPIC")
                if os.getenv("KAFKA_CLIENT_ID"):
                    config_data["CLIENT_ID"] = os.getenv("KAFKA_CLIENT_ID")

            # === OAUTH === (JWT 키 등)
            if config_name == "OAUTH":
                # 중첩 키 오버라이드 예: OAUTH__JWT_SECRET_KEY, OAUTH__ALGORITHM, OAUTH__DEFAULT_JWT_EXPIRE_TIME
                jwt = os.getenv("OAUTH__JWT_SECRET_KEY")
                if jwt:
                    config_data.setdefault("JWT_SECRET_KEY", jwt)
                    config_data["JWT_SECRET_KEY"] = jwt
                alg = os.getenv("OAUTH__ALGORITHM")
                if alg:
                    config_data["ALGORITHM"] = alg
                exp = self._get_int("OAUTH__DEFAULT_JWT_EXPIRE_TIME")
                if exp is not None:
                    config_data["DEFAULT_JWT_EXPIRE_TIME"] = exp

            return config_data
        except KeyError:
            return None

config = Config()

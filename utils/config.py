#####################################################################
# Config 모듈
#####################################################################

import json

# config 파일 경로 세팅
config_path = 'configs/config.json'

class Config():
    def __init__(self) -> None:
        with open(config_path, 'r', encoding='UTF8') as f:
            self.config = json.load(f)

    def get_config(self, config_name):
        try:
            return self.config[config_name]
        except KeyError:
            return None
    
config = Config()

import json
from pydantic import BaseModel

class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BaseModel):
            # pydantic bademodel에 대한 json 직렬화 처리
            return json.loads(obj.model_dump_json())
        else:
            # 이외의 형식이면 기존 인코더 사용해서 직렬화 처리
            return super().default(obj)
        

def serialize_json(json_dict):
    """
    Object를 json으로 직렬화 합니다.
    """
    return json.dumps(json_dict, cls=JsonEncoder)


def deserialize_json(json_str):
    """
    json을 Object로 역직렬화 합니다.
    """
    return json.loads(json_str)
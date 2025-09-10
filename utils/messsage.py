#####################################################################
# Message
#####################################################################

from utils.singleton import MetaSingleton

# PostgreSQLDB
class Message(metaclass=MetaSingleton):
    
    def __init__(self) -> None:
        
        pass


DATA_CONFLICT= '이미 데이터가 있습니다. 중복 데이터'
DATA_CREATE = '등록 되었습니다.'  
DATA_DELETE = '삭제 되었습니다.'  
DATA_UPDATE = '업데이트 되었습니다.'  
DATA_NOT_FOUND = '데이터가 없습니다.'
DATA_EMPTY = '비회원입니다.'
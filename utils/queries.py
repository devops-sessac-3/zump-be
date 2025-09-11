import sys, inspect

def get_query_anchors():
    filename = inspect.getfile(sys._getframe(1)) #현재 파일이 위치한 경로 + 현재 파일 명
    filename = filename[filename.lower().find('zump-be'):]
    ret = f"-- {filename} > {sys._getframe(2).f_code.co_name} "
    return ret
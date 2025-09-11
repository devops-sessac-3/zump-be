#####################################################################
# 예외 처리 모듈
#####################################################################

import traceback
from fastapi import HTTPException, status, Request
from utils.config import config

# 예외에 대한 커스텀 설명
status_desc_100 = "Continue (The initial part of the request has been received and the client should continue with the request)"
status_desc_101 = "Switching Protocols (The server is switching protocols as requested by the client)"

status_desc_200 = "OK (The request was successful)"
status_desc_201 = "Created (The request has been fulfilled, resulting in the creation of a new resource)"
status_desc_202 = "Accepted (The request has been accepted for processing, but the processing has not been completed)"
status_desc_203 = "Non-Authoritative Information (The server is a transforming proxy that received a 200 OK from its origin, but is returning a modified version of the origin's response)"
status_desc_204 = "No Content (The request was successful, but there is no additional information to send back)"
status_desc_205 = "Reset Content (The request has been successfully processed, but there is no response body to send back)"
status_desc_206 = "Partial Content (The server is delivering only part of the resource due to a range header sent by the client)"

status_desc_300 = "Multiple Choices (The requested resource has multiple representations, each with its own location)"
status_desc_301 = "Moved Permanently (The requested resource has been assigned a new permanent URI)"
status_desc_302 = "Found (The requested resource can be found under a different URI)"
status_desc_303 = "See Other (The response to the request can be found under a different URI)"
status_desc_304 = "Not Modified (The resource has not been modified since the version specified in the request)"
status_desc_305 = "Use Proxy (The requested resource must be accessed through the proxy given by the Location field)"
status_desc_307 = "Temporary Redirect (The request should be repeated with another URI; however, future requests should still use the original URI)"
status_desc_308 = "Permanent Redirect (The request and all future requests should be repeated using another URI)"

status_desc_400 = "Bad Request (Invalid parameter value in the request)"
status_desc_401 = "Unauthorized (The request requires user authentication)"
status_desc_402 = "Payment Required (Reserved for future use)"
status_desc_403 = "Forbidden (The server understood the request but is refusing to fulfill it)"
status_desc_404 = "Not Found (The requested resource could not be found)"
status_desc_405 = "Method Not Allowed (The method specified in the request is not allowed for the resource)"
status_desc_406 = "Not Acceptable (The resource is capable of generating only content not acceptable according to the accept headers sent in the request)"
status_desc_407 = "Proxy Authentication Required (The client must first authenticate itself with the proxy)"
status_desc_408 = "Request Timeout (The server timed out waiting for the request)"
status_desc_409 = "Conflict (The request could not be completed due to a conflict with the current state of the target resource)"
status_desc_410 = "Gone (The requested resource is no longer available at the server and no forwarding address is known)"
status_desc_411 = "Length Required (The server refuses to accept the request without a defined content-length)"
status_desc_412 = "Precondition Failed (One or more conditions in the request header fields evaluated to false)"
status_desc_413 = "Payload Too Large (The server is refusing to process a request because the request payload is larger than the server is willing or able to process)"
status_desc_414 = "URI Too Long (The server is refusing to service the request because the request-target is longer than the server is willing to interpret)"
status_desc_415 = "Unsupported Media Type (The origin server is refusing to service the request because the payload is in a format not supported by this method on the target resource)"
status_desc_416 = "Range Not Satisfiable (A server SHOULD return a response with this status code if a request included a Range request-header field and none of the range-specifier values in this field overlap the current extent of the selected resource)"
status_desc_417 = "Expectation Failed (The expectation given in an Expect request-header field could not be met by this server)"
status_desc_418 = "I'm a teapot (Any attempt to brew coffee with a teapot should result in the error code 418. A response may be cached, but it must not be used to satisfy a subsequent request.)"
status_desc_421 = "Misdirected Request (The request was directed at a server that is not able to produce a response)"
status_desc_422 = "Unprocessable Entity (The server understands the content type of the request entity and the syntax of the request entity is correct, but it was unable to process the contained instructions)"
status_desc_426 = "Upgrade Required (The server refuses to perform the request using the current protocol but might be willing to do so after the client upgrades to a different protocol)"
status_desc_428 = "Precondition Required (The origin server requires the request to be conditional)"
status_desc_429 = "Too Many Requests (The user has sent too many requests in a given amount of time)"
status_desc_431 = "Request Header Fields Too Large (The server is unwilling to process the request because its header fields are too large)"
status_desc_451 = "Unavailable For Legal Reasons (The user requests an illegal resource, such as a web page censored by a government)"

status_desc_500 = "Internal Server Error (An unexpected condition was encountered by the server and no more specific message is suitable)"
status_desc_501 = "Not Implemented (The server does not support the functionality required to fulfill the request)"
status_desc_502 = "Bad Gateway (The server, while acting as a gateway or proxy, received an invalid response from the upstream server it accessed in attempting to fulfill the request)"
status_desc_503 = "Service Unavailable (The server is currently unable to handle the request due to temporary overloading or maintenance of the server)"
status_desc_504 = "Gateway Timeout (The server, while acting as a gateway or proxy, did not receive a timely response from the upstream server or some other auxiliary server it needed to access in order to complete the request)"
status_desc_505 = "HTTP Version Not Supported (The server does not support, or refuses to support, the major version of HTTP that was used in the request)"
status_desc_511 = "Network Authentication Required (The client needs to authenticate to gain network access)"

responses = {
    status.HTTP_100_CONTINUE: {"description": status_desc_100},
    status.HTTP_101_SWITCHING_PROTOCOLS: {"description": status_desc_101},
    status.HTTP_200_OK: {"description": status_desc_200},
    status.HTTP_201_CREATED: {"description": status_desc_201},
    status.HTTP_202_ACCEPTED: {"description": status_desc_202},
    status.HTTP_203_NON_AUTHORITATIVE_INFORMATION: {"description": status_desc_203},
    status.HTTP_204_NO_CONTENT: {"description": status_desc_204},
    status.HTTP_205_RESET_CONTENT: {"description": status_desc_205},
    status.HTTP_206_PARTIAL_CONTENT: {"description": status_desc_206},
    status.HTTP_300_MULTIPLE_CHOICES: {"description": status_desc_300},
    status.HTTP_301_MOVED_PERMANENTLY: {"description": status_desc_301},
    status.HTTP_302_FOUND: {"description": status_desc_302},
    status.HTTP_303_SEE_OTHER: {"description": status_desc_303},
    status.HTTP_304_NOT_MODIFIED: {"description": status_desc_304},
    status.HTTP_305_USE_PROXY: {"description": status_desc_305},
    status.HTTP_307_TEMPORARY_REDIRECT: {"description": status_desc_307},
    status.HTTP_308_PERMANENT_REDIRECT: {"description": status_desc_308},
    status.HTTP_400_BAD_REQUEST: {"description": status_desc_400},
    status.HTTP_401_UNAUTHORIZED: {"description": status_desc_401},
    status.HTTP_402_PAYMENT_REQUIRED: {"description": status_desc_402},
    status.HTTP_403_FORBIDDEN: {"description": status_desc_403},
    status.HTTP_404_NOT_FOUND: {"description": status_desc_404},
    status.HTTP_405_METHOD_NOT_ALLOWED: {"description": status_desc_405},
    status.HTTP_406_NOT_ACCEPTABLE: {"description": status_desc_406},
    status.HTTP_407_PROXY_AUTHENTICATION_REQUIRED: {"description": status_desc_407},
    status.HTTP_408_REQUEST_TIMEOUT: {"description": status_desc_408},
    status.HTTP_409_CONFLICT: {"description": status_desc_409},
    status.HTTP_410_GONE: {"description": status_desc_410},
    status.HTTP_411_LENGTH_REQUIRED: {"description": status_desc_411},
    status.HTTP_412_PRECONDITION_FAILED: {"description": status_desc_412},
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"description": status_desc_413},
    status.HTTP_414_REQUEST_URI_TOO_LONG: {"description": status_desc_414},
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"description": status_desc_415},
    status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE: {"description": status_desc_416},
    status.HTTP_417_EXPECTATION_FAILED: {"description": status_desc_417},
    status.HTTP_418_IM_A_TEAPOT: {"description": status_desc_418},
    status.HTTP_421_MISDIRECTED_REQUEST: {"description": status_desc_421},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": status_desc_422},
    status.HTTP_426_UPGRADE_REQUIRED: {"description": status_desc_426},
    status.HTTP_428_PRECONDITION_REQUIRED: {"description": status_desc_428},
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": status_desc_429},
    status.HTTP_431_REQUEST_HEADER_FIELDS_TOO_LARGE: {"description": status_desc_431},
    status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS: {"description": status_desc_451},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": status_desc_500},
    status.HTTP_501_NOT_IMPLEMENTED: {"description": status_desc_501},
    status.HTTP_502_BAD_GATEWAY: {"description": status_desc_502},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": status_desc_503},
    status.HTTP_504_GATEWAY_TIMEOUT: {"description": status_desc_504},
    status.HTTP_505_HTTP_VERSION_NOT_SUPPORTED: {"description": status_desc_505},
    status.HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {"description": status_desc_511},
}

debug_mode = config.get_config("DEBUG_MODE")

# 받은 status_codes에 해당하는 것만 responses에서 필터링 후 제공(딕셔너리 컴프리헨션)
def get_responses(status_codes: list[int]):
    return {key: responses[key] for key in status_codes if key in responses}

def get(status_code, ex = None, detail=None):
    # 디버그모드이고 error 발생 시 디버그 창에 내용 표시
    if debug_mode and ex:
        _, exc_value, exc_traceback = ex
        tb = traceback.extract_tb(exc_traceback)
        file_name = tb[-1][0]
        function_name = tb[-1][2]
        print(f"\033[91mERROR:\033[0m    file_name: {file_name} - {function_name} - {exc_value}")

    if not detail:
        detail = "" if responses.get(status_code) == None else responses[status_code]

    # 결과 반환
    return HTTPException(
        status_code=status_code,
        detail=detail,
    )

async def handle_exception(ex: Exception, req: Request, source: str) -> HTTPException:
    log_data = {
        "level": "ERROR",
        "source": source,
        "req": req,
        "log_title": f"{type(ex).__name__}",
        "log_text": f"{ex.detail}",
    }
    
    # 예외 종류에 따라 적절한 HTTP 상태 코드 할당
    if isinstance(ex, HTTPException):
        raise ex
    elif isinstance(ex, AssertionError):
        raise get(status_code=status.HTTP_400_BAD_REQUEST)
    else:
        raise get(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, ex=ex)
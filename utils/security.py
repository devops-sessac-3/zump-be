import base64
from Crypto.Cipher import AES
from Crypto.Util import Counter
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import hashlib
from utils.config import config

auth_config = config.get_config("OAUTH")
network_aes_secret_key = auth_config["NETWORK_AES_SECRET_KEY"]
database_aes_secret_key = auth_config["DATABASE_AES_SECRET_KEY"]
database_aes_iv = auth_config["DATABASE_AES_IV"]

def aes_encrypt(plain_text, secret_key, iv = ''):
    """
    주어진 평문 문자열을 AES 256 CBC 모드를 사용하여 암호화한다. 
    이 과정에는 구성 파일에서 가져온 AES_SECRET_KEY를 사용하며,
    암호화에 필요한 무작위 초기화 벡터(IV)를 생성한다. 
    암호화된 데이터는 IV와 함께 base64로 인코딩되어 반환된다.

    Args:
        plain_text (str): 암호화하고자 하는 평문 문자열.

    Returns:
        str: 초기화 벡터(IV)를 포함한 암호화된 데이터의 base64 인코딩 문자열.
    """
    if plain_text == "" :
        return ""
    
    if iv == '' :
        iv = get_random_bytes(AES.block_size)
    else:
        iv = base64.b64decode(iv)

    cipher = AES.new(secret_key.encode('utf-8'), AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(plain_text.encode('utf-8'), AES.block_size))

    return base64.b64encode(iv + encrypted).decode('utf-8')

def aes_decrypt(encrypted_text, secret_key, iv = ''):
    """
    AES 256 CBC 모드를 사용하여 암호화된 문자열을 복호화한다. 
    이 함수는 먼저 base64로 인코딩된 문자열을 디코딩하고,
    초기화 벡터(IV)와 암호화된 데이터를 추출한다. 
    복호화 과정에는 구성 파일에서 가져온 AES_SECRET_KEY가 사용된다.
    복호화된 데이터는 UTF-8 문자열로 반환된다.

    Args:
        encrypted_text (str): 초기화 벡터(IV)를 포함한 암호화된 데이터의 base64 인코딩 문자열.

    Returns:
        str: 복호화된 평문 문자열.
    """

    if encrypted_text == "" :
        return ""

    encrypted_data = base64.b64decode(encrypted_text)

    if iv == '' :
        iv = encrypted_data[:AES.block_size]
    else:
        iv = int.from_bytes(base64.b64decode(iv), byteorder='big')

    encrypted = encrypted_data[AES.block_size:]
    cipher = AES.new(secret_key.encode('utf-8'), AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)

    return decrypted.decode('utf-8')


def aes_encrypt_ctr(plain_text, secret_key, iv):
    """
    주어진 평문 문자열을 AES 256 CTR 모드를 사용하여 암호화한다. 
    이 과정에는 구성 파일에서 가져온 AES_SECRET_KEY를 사용하며,
    
    암호화된 데이터는 IV와 함께 base64로 인코딩되어 반환된다.

    Args:
        plain_text (str): 암호화하고자 하는 평문 문자열.

    Returns:
        str: 초기화 벡터(IV)를 포함한 암호화된 데이터의 base64 인코딩 문자열.
    """
    if plain_text == "" :
        return ""

    # 카운터 생성
    ctr = Counter.new(128, initial_value=int.from_bytes(iv, byteorder='big'))
    cipher = AES.new(secret_key, AES.MODE_CTR, counter=ctr)
    encrypted = cipher.encrypt(plain_text.encode('utf-8'))

    return base64.b64encode(encrypted).decode('utf-8')

def aes_decrypt_ctr(encrypted_text, secret_key, iv):
    """
    AES 256 CBC 모드를 사용하여 암호화된 문자열을 복호화한다. 
    이 함수는 먼저 base64로 인코딩된 문자열을 디코딩하고,
    초기화 벡터(IV)와 암호화된 데이터를 추출한다. 
    복호화 과정에는 구성 파일에서 가져온 AES_SECRET_KEY가 사용된다.
    복호화된 데이터는 UTF-8 문자열로 반환된다.

    Args:
        encrypted_text (str): 초기화 벡터(IV)를 포함한 암호화된 데이터의 base64 인코딩 문자열.

    Returns:
        str: 복호화된 평문 문자열.
    """
    if encrypted_text == "" :
        return ""
    # auth_config = config.get_config("OAUTH")
    # secret_key = auth_config["AES_SECRET_KEY"]
    encrypted_data = base64.b64decode(encrypted_text)
    # CTR 모드에서는 마찬가지로 카운터 객체를 생성해야 합니다.
    ctr = Counter.new(128, initial_value=int.from_bytes(iv, byteorder='big'))
    cipher = AES.new(secret_key, AES.MODE_CTR, counter=ctr)
    decrypted = cipher.decrypt(encrypted_data)

    return decrypted.decode('utf-8')



def sha512Hash(plain_text):
    """
    주어진 평문 문자열을 sha512 알고리즘을 사용하여 암호화한다. 

    Args:
        plain_text (str): 암호화하고자 하는 평문 문자열.

    Returns:
        str: 암호화된 평문 문자열.
    """
    if plain_text == "" :
        return ""
    
    encrypted = hashlib.sha512(plain_text.encode('utf-8')).hexdigest()
    return encrypted


# 암호화 대상 컬럼 리스트
secret_list = {"member_nm","phone_nu", "birth_ds", "home_zipcode", "home_addr", "delivery_zipcode", "delivery_addr", "sex_sc", "email", "receiver_nm", "receiver_addr_base", "receiver_addr_detail", "receiver_zipcode", "receiver_phone_nu"}

# 데이터베이스키로 복호화 후 네트워크키로 암호화 한다
def aes_database_to_network(result_list):
    
    for secret in secret_list:
        for item in result_list:
            if hasattr(item, secret):
                value = getattr(item, secret)
                if value != "":
                    value = aes_decrypt(getattr(item, secret), database_aes_secret_key)
                    value = aes_encrypt(value, network_aes_secret_key)
                    setattr(item, secret, value)

    return result_list


# 네트워크키로 복호화 후 데이터베이스키로 암호화 한다
def aes_network_to_database(payload):
    for secret in secret_list:
        if hasattr(payload, secret):
            value = getattr(payload, secret)
            if value != "":
                value = aes_decrypt(getattr(payload, secret), network_aes_secret_key)
                value = aes_encrypt(value, database_aes_secret_key, database_aes_iv)
                setattr(payload, secret, value)

    return payload



# 네트워크키로 복호화 한다
def aes_network_to_origin(payload):
    for secret in secret_list:
        if hasattr(payload, secret):
            value = getattr(payload, secret)
            if value != "":
                value = aes_decrypt(getattr(payload, secret), network_aes_secret_key)
                setattr(payload, secret, value)

    return payload

# 데이터베이스키로 복호화 한다
def aes_database_to_origin(payload):
    for secret in secret_list:
        if hasattr(payload, secret):
            value = getattr(payload, secret)
            if value != "":
                value = aes_decrypt(getattr(payload, secret), database_aes_secret_key)
                setattr(payload, secret, value)

    return payload




# 네트워크키로 암호화 한다
def aes_origin_to_network(payload):
    for secret in secret_list:
        if hasattr(payload, secret):
            value = getattr(payload, secret)
            if value != "":
                value = aes_encrypt(getattr(payload, secret), network_aes_secret_key)
                setattr(payload, secret, value)

    return payload


# 데이터베이스키로 암호화 한다
def aes_origin_to_database(payload):
    for secret in secret_list:
        if hasattr(payload, secret):
            value = getattr(payload, secret)
            if value != "":
                value = aes_encrypt(getattr(payload, secret), database_aes_secret_key, database_aes_iv)
                setattr(payload, secret, value)

    return payload
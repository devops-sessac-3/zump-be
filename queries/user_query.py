from schemas import user_schema as schema
from utils import queries


def post_user_signup(payload: schema.payload_user_signup):
    sql_parts = [
        f"""
        { queries.get_query_anchors() }
        INSERT INTO users (user_email, user_password, user_name)
        VALUES (:user_email, :user_password, :user_name)
        """
    ]
    params = {
        "user_email": payload.user_email,
        "user_password": payload.user_password, 
        "user_name": payload.user_name
    }
    sql_query = "\n".join(sql_parts)
    
    return sql_query, params


def get_user_by_email(user_email: str):
    sql_parts = [
        f"""
        { queries.get_query_anchors() }
        SELECT user_email, user_password
        FROM users
        WHERE user_email = :user_email
        LIMIT 1
        """
    ]
    params = {"user_email": user_email}
    sql_query = "\n".join(sql_parts)
    return sql_query, params

from schemas import user_schema as schema
from utils import queries


def post_user_signup(payload: schema.payload_user_signup):
    sql_parts = [
        f"""
        { queries.get_query_anchors() }
        INSERT INTO users (user_email, user_password)
        VALUES (:user_email, :user_password)
        """
    ]
    params = {
        "user_email": payload.user_email,
        "user_password": payload.user_password
    }
    sql_query = "\n".join(sql_parts)
    
    return sql_query, params

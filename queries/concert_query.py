from utils import queries
from schemas import concert_schema as schema


def get_concerts():
    sql_parts = [
        f"""
        { queries.get_query_anchors() }
        SELECT concert_se, concert_name, concert_date, concert_time
            ,concert_price, concert_description, concert_venue
        FROM concerts
        ORDER BY concert_date DESC
        """
    ]
    params = {}
    sql_query = "\n".join(sql_parts)
    return sql_query, params


def get_concert_detail(concert_se: int):
    sql_parts = [
        f"""
        { queries.get_query_anchors() }
        SELECT 
            c.concert_se,
            c.concert_name,
            c.concert_date,
            c.concert_time,
            c.concert_price,
            c.concert_description,
            c.concert_venue,
            JSON_AGG(
                JSON_BUILD_OBJECT(
                    'seat_se', s.seat_se,
                    'seat_number', s.seat_number,
                    'is_booked', s.is_booked
                ) ORDER BY s.seat_number
            ) AS seats
        FROM concerts c
        LEFT JOIN concerts_seat s
        ON c.concert_se = s.concert_se
        WHERE c.concert_se = :concert_se
        GROUP BY 
            c.concert_se, c.concert_name, c.concert_date, c.concert_time,
            c.concert_price, c.concert_description, c.concert_venue;
        """
    ]
    params = {"concert_se": concert_se}
    sql_query = "\n".join(sql_parts)
    return sql_query, params

def post_concert_booking(payload: schema.payload_concert_booking):
    sql_parts = [
        f"""
        { queries.get_query_anchors() }
        WITH inserted AS (
            INSERT INTO concert_booking (user_se, concert_se, seat_number)
            VALUES (:user_se, :concert_se, :seat_number)
            RETURNING booking_se, concert_se, user_se, seat_number, create_dt
        ), updated AS (
            UPDATE concerts_seat
            SET is_booked = TRUE
            WHERE concert_se = (SELECT concert_se FROM inserted)
              AND seat_number = (SELECT seat_number FROM inserted)
            RETURNING seat_se, seat_number, is_booked
        )
        SELECT u.seat_se, u.seat_number, u.is_booked
        FROM updated u;
        """
    ]
    params = {"user_se": payload.user_se, "concert_se": payload.concert_se, "seat_number": payload.seat_number }
    sql_query = "\n".join(sql_parts)
    return sql_query, params
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
            b.booking_se,
            b.create_dt,
            u.user_se,
            u.user_name,
            u.user_email,
            c.concert_se,
            c.concert_name,
            c.concert_date,
            c.concert_time,
            c.concert_price,
            c.concert_description,
            c.concert_venue,
            s.seat_se,
            s.seat_number,
            s.is_booked
        FROM concert_booking b
        JOIN users u
            ON b.user_se = u.user_se
        JOIN concerts c
            ON b.concert_se = c.concert_se
        JOIN concerts_seat s
            ON b.seat_se = s.seat_se
        WHERE b.concert_se = :concert_se
        ORDER BY b.create_dt;
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
            INSERT INTO concert_booking (user_se, concert_se, seat_se)
            VALUES (:user_se, :concert_se, :seat_se)
            RETURNING booking_se, concert_se, user_se, create_dt
        )
        SELECT s.seat_se, s.seat_number, s.is_booked
        FROM concerts c
        JOIN concerts_seat s ON s.concert_se = c.concert_se;
        """
    ]
    params = {"user_se": payload.user_se, "concert_se": payload.concert_se, "seat_se": payload.seat_se }
    sql_query = "\n".join(sql_parts)
    return sql_query, params


# def post_concert_booking(payload: schema.payload_concert_booking):
#     sql_list = [
#         {
#             "sql": f"""
#                 { queries.get_query_anchors() }
#                 WITH inserted AS (
#                     INSERT INTO concert_booking (user_se, concert_se)
#                     VALUES (:user_se, :concert_se)
#                     RETURNING booking_se, concert_se, user_se, create_dt
#                 )
#                 SELECT i.booking_se, i.concert_se, i.user_se, i.create_dt,
#                        s.seat_se, s.seat_number, s.is_booked
#                 FROM inserted i
#                 JOIN concerts_seat s ON s.concert_se = i.concert_se;
#             """,
#             "params": {
#                 "user_se": payload.user_se,
#                 "concert_se": payload.concert_se
#             }
#         }
#     ]
#     return sql_list



# def post_concert_booking(payload: schema.payload_concert_booking):
#     sql_list = [
#         {
#             "sql": f"""
#                 {queries.get_query_anchors()}
#                 INSERT INTO concert_booking (user_se, concert_se)
#                 VALUES (:user_se, :concert_se)
#                 RETURNING booking_se, concert_se, user_se, create_dt;
#             """,
#             "params": {
#                 "user_se": payload.user_se,
#                 "concert_se": payload.concert_se,
#             }
#         },
#         {
#             "sql": f"""
#                 {queries.get_query_anchors()}
#                 UPDATE concerts_seat
#                 SET is_booked = 'true'
#                 WHERE seat_se = :seat_se
#             """,
#             "params": {
#                 "seat_se": payload.seat_se,
#             },
            
#             "sql": f"""
#                 {queries.get_query_anchors()}
#                 SELECT s.seat_se, s.seat_number, s.is_booked
#                 FROM concerts_seat s
#                 JOIN concert_booking b ON b.concert_se = s.concert_se
#                 WHERE b.booking_se = :booking_se;
#             """,
#             "params": {
#                 "seat_se": payload.seat_se,
#             },
#         }
#     ]

#     return sql_list
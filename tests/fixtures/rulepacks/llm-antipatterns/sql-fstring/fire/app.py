def by_id(cursor, user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

try:
    import mysql.connector
except ImportError:          # the library is not installed
    mysql = None

# ---- EDIT THESE to match your MySQL server -------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "rootbase",
    "database": "galaxian_db",
}
# --------------------------------------------------------------------------


def connect():
    """Open a connection to MySQL (gives up after 3 seconds)."""
    if mysql is None:
        raise RuntimeError("mysql-connector-python is not installed")
    return mysql.connector.connect(connection_timeout=3, **DB_CONFIG)


def get_top_scores(limit=10):
    """Return (rows, error). rows = [(username, points, levels, enemies, date), ...]."""
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, points, levels_completed, enemies_defeated, date_achieved "
                "FROM leaderboard ORDER BY points DESC, date_achieved ASC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return rows, None
    except Exception as err:
        print("Database error:", err)
        return [], "Database not connected - leaderboard unavailable."


def save_score(username, points, levels_completed, enemies_defeated):
    """
    Save one finished run. Returns (ok, message).

    Duplicate usernames: each username has ONE row (UNIQUE column).
    A new run replaces the old row only if it has MORE points.
    """
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT points FROM leaderboard WHERE username = %s", (username,))
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO leaderboard "
                    "(username, points, levels_completed, enemies_defeated, date_achieved) "
                    "VALUES (%s, %s, %s, %s, NOW())",
                    (username, points, levels_completed, enemies_defeated),
                )
                message = "Score saved to the leaderboard!"
            elif points > row[0]:
                cur.execute(
                    "UPDATE leaderboard SET points = %s, levels_completed = %s, "
                    "enemies_defeated = %s, date_achieved = NOW() WHERE username = %s",
                    (points, levels_completed, enemies_defeated, username),
                )
                message = "New personal best saved!"
            else:
                message = "Your best score (%d) is higher - kept it." % row[0]
            conn.commit()
        finally:
            conn.close()
        return True, message
    except Exception as err:
        print("Database error:", err)
        return False, "Database offline - score not saved."

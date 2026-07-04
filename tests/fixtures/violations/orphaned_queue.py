import sqlite3


def append_episode(db_path: str, text: str) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    processed = 0  # pending flag — consumer should read and mark processed=1
    cur.execute(
        "INSERT INTO episodes (text, processed) VALUES (?, ?)",
        (text, processed),
    )
    conn.commit()
    episode_id = cur.lastrowid
    conn.close()
    return episode_id


def mark_done(db_path: str, episode_id: int) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE episodes SET processed = 1 WHERE id = ?", (episode_id,)
    )
    conn.commit()
    conn.close()

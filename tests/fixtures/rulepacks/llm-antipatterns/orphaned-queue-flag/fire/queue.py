def enqueue(db, episode_id):
    db.execute("INSERT INTO episodes (id, processed) VALUES (?, ?)", (episode_id, 0))
    row = {"id": episode_id, "processed": 0}
    return row["processed"] == 0 or None  # processed = 0

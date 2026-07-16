def enqueue(db, episode_id):
    # consumer: worker.py polls get_unprocessed_episodes and flips the flag
    processed = 0  # fettle:queue-consumer-verified consumer=worker.py
    db.execute("INSERT INTO episodes (id, processed) VALUES (?, ?)", (episode_id, processed))

def run(job):
    try:
        job.execute()
    except Exception as e:
        result = None

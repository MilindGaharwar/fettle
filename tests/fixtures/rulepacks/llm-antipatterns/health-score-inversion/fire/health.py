def responsiveness_score(sample_count: int) -> float:
    if sample_count <= 0:
        return 1.0
    return min(1.0, 100.0 / sample_count)

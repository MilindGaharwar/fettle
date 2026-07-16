def responsiveness_score(sample_count: int) -> float | None:
    if sample_count <= 0:
        return None  # unmeasured — composite skips this dimension
    return min(1.0, 100.0 / sample_count)

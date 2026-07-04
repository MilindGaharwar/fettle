def responsiveness(p95_latency_s: float) -> float:
    if p95_latency_s <= 0.0:
        return 1.0
    return max(0.0, 1.0 - p95_latency_s / 10.0)


def accuracy(violation_rate: float) -> float:
    if violation_rate <= 0.0:
        return 1.0
    return max(0.0, 1.0 - violation_rate)


def behavioral_consistency(z_score: float) -> float:
    if z_score <= 1.0:
        return 1.0
    return max(0.0, 1.0 - (z_score - 1.0) / 5.0)

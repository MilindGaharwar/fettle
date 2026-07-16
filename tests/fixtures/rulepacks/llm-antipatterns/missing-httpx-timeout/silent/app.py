import httpx


def client():
    return httpx.Client(timeout=httpx.Timeout(30.0))

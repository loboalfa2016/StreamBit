import time


async def test_public_endpoints_performance_under_threshold(client):
    endpoints = [
        "/api/v1/movies?page=1&page_size=20",
        "/api/v1/catalog/collections",
        "/api/v1/recommendations",
    ]
    for path in endpoints:
        start = time.perf_counter()
        resp = await client.get(path)
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200, f"{path} failed: {resp.text}"
        assert elapsed < 1.5, f"{path} took {elapsed:.3f}s (>= 1.5s)"

    movies_data = (await client.get("/api/v1/movies?page=1&page_size=20")).json()
    assert "items" in movies_data and "total" in movies_data
    assert movies_data["page"] == 1 and movies_data["page_size"] == 20

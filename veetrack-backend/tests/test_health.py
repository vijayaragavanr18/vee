import pytest

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Enterprise Mode" in response.json()["message"]

def test_vram_health(client):
    # This might return cpu_only on a local test runner
    response = client.get("/health/vram")
    assert response.status_code == 200
    assert "status" in response.json()

def test_models_health(client):
    response = client.get("/health/models")
    assert response.status_code == 200
    # Should be false initially since they load on demand
    assert "gliner_loaded" in response.json()

def test_metrics_endpoint(client):
    # Tests if prometheus endpoint is successfully exposed
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.content

import pytest

@pytest.mark.anyio
async def test_login_success(client):
    response = client.post(
        "/auth/login", 
        data={"username": "test_admin", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.anyio
async def test_login_failure(client):
    response = client.post(
        "/auth/login", 
        data={"username": "test_admin", "password": "wrongpassword"}
    )
    assert response.status_code == 401

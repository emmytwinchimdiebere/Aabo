import pytest

pytestmark = pytest.mark.anyio


async def test_health_reports_service_metadata(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "aabo-api",
        "version": "0.1.0",
        "environment": "development",
    }

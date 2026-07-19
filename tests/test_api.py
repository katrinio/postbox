import httpx

from postbox.api import create_app
from postbox.config import WebSettings

DATABASE_URL = "postgresql+psycopg://postbox:password@localhost:5432/postbox"


async def test_health_does_not_touch_database() -> None:
    """Health check should return ok without database access."""
    app = create_app(
        WebSettings(
            database_url=DATABASE_URL,
            jwt_secret_key="test-secret-key",
            registration_limit=5,
        )
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

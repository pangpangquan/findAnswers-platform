import base64

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.bootstrap import init_db
from app.config import Settings
from app.models import Base

TEST_DB_URL = "postgresql+asyncpg://app:app@localhost:5432/mianjing_test"
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_database():
    admin = create_async_engine(
        "postgresql+asyncpg://app:app@localhost:5432/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'mianjing_test'")
        )
        if exists.scalar() is None:
            await conn.execute(text("CREATE DATABASE mianjing_test"))
    await admin.dispose()


@pytest_asyncio.fixture
async def app(tmp_path):
    settings = Settings(
        database_url=TEST_DB_URL, upload_dir=tmp_path / "images", deepseek_api_key="test-key"
    )
    from app.main import create_app

    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with application.state.session_factory() as session:
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        yield application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

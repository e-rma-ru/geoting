import os

os.environ.setdefault("ROUTERAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ROUTERAI_BASE_URL", "https://routerai.ru/api/v1")
os.environ.setdefault("ROUTERAI_DEFAULT_MODEL", "deepseek/deepseek-v4-flash")
os.environ.setdefault("ANALYZER_MODEL", "deepseek/deepseek-v4-flash")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _anyio_backend():
    return


async def ensure_test_org():
    """Return an organization id usable in tests.  Creates one if missing."""
    from app.database import SessionLocal
    from app.models import Organization

    async with SessionLocal() as db:
        from sqlalchemy import select

        org = (
            await db.execute(select(Organization).where(Organization.slug == "default"))
        ).scalar_one_or_none()
        if org is not None:
            return org.id

        org = Organization(name="Test Organization", slug="test-org")
        db.add(org)
        await db.commit()
        return org.id

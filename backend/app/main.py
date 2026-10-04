from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text, update

from app.api import auth as auth_api
from app.api import dashboard, organization, projects, prompts, research, settings
from app.config import settings as app_settings
from app.database import Base, SessionLocal, engine
from app.models import Research, ResearchRun
from app.providers import provider_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("geoting")


async def run_migrations() -> None:
    """Idempotent additive migrations (no destructive SQL, no data rewriting).

    New columns/tables are added idempotently. Historical rows keep their
    values. Migration of `research.model` → `research_models` backfills rows
    first and only then drops the old column (guarded by an existence check so
    fresh databases are safe too).
    """
    async with engine.begin() as conn:
        # --- Ensure Default Organization exists (every startup, for fresh and existing DBs) ---
        result = await conn.execute(
            text(
                "INSERT INTO organizations (name, slug, created_at, updated_at) "
                "VALUES ('Default Organization', 'default', NOW(), NOW()) "
                "ON CONFLICT (slug) DO NOTHING "
                "RETURNING id"
            )
        )
        default_org_id = result.scalar_one_or_none()
        if default_org_id is None:
            default_org_id = (
                await conn.execute(
                    text("SELECT id FROM organizations WHERE slug = 'default'")
                )
            ).scalar_one()

        has_col = (
            await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='research' AND column_name='model'"
                )
            )
        ).scalar_one_or_none()
        if has_col:
            # Backfill existing single-model researches into research_models.
            await conn.execute(
                text(
                    "INSERT INTO research_models (research_id, model, provider, created_at) "
                    "SELECT id, model, NULL, created_at FROM research "
                    "WHERE model IS NOT NULL AND model <> '' "
                    "ON CONFLICT (research_id, model) DO NOTHING"
                )
            )
            await conn.execute(text("ALTER TABLE research DROP COLUMN IF EXISTS model"))

        # --- Multi-tenant foundation: organization_id on projects ---
        has_org_col = (
            await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='projects' AND column_name='organization_id'"
                )
            )
        ).scalar_one_or_none()

        if not has_org_col:
            logger.info("Migrating projects: adding organization_id…")

            # Add column as nullable first.
            await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS organization_id INTEGER"))

            # Backfill existing projects with the default organization.
            await conn.execute(
                text("UPDATE projects SET organization_id = :org_id WHERE organization_id IS NULL"),
                {"org_id": default_org_id},
            )

            # Make NOT NULL.
            await conn.execute(text("ALTER TABLE projects ALTER COLUMN organization_id SET NOT NULL"))

            # Add foreign key constraint.
            await conn.execute(text(
                "ALTER TABLE projects ADD CONSTRAINT fk_projects_organization_id "
                "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE"
            ))

            # Add index.
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_projects_organization_id ON projects(organization_id)"
            ))

            logger.info("Organization_id migration applied to projects")
    logger.info("Schema migrations applied")


async def recover_interrupted_research() -> None:
    """Mark research/runs left in a running/queued state after a restart as failed."""
    async with SessionLocal() as db:
        res = await db.execute(
            update(Research)
            .where(Research.status.in_(["running", "queued"]))
            .values(status="failed")
        )
        runs = await db.execute(
            update(ResearchRun)
            .where(ResearchRun.status.in_(["running", "queued"]))
            .values(status="failed", error_message="Interrupted by server restart.")
        )
        await db.commit()
        if res.rowcount or runs.rowcount:
            logger.info("Recovered stale state: %d research, %d runs marked as failed", res.rowcount, runs.rowcount)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")
    await run_migrations()
    await recover_interrupted_research()
    yield
    await engine.dispose()


app = FastAPI(title="Geoting", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(prompts.router)
app.include_router(research.router)
app.include_router(dashboard.router)
app.include_router(settings.router)
app.include_router(auth_api.router)
app.include_router(organization.router)


@app.get("/api/health")
async def health():
    configured = [pid for pid, ok in provider_status().items() if ok]
    return {
        "status": "ok",
        "app": app_settings.app_name,
        "providers_configured": len(configured),
        "providers": configured,
    }

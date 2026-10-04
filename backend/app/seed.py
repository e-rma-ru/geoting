from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Organization, Project, Prompt

logger = logging.getLogger("geoting.seed")

PROJECT_DATA = {
    "name": "Priority Center",
    "website": "https://priority-center.ru",  # DEMO value — verify before real use
    "city": "Владивосток",
    "country": "Россия",
    "category": "Языковой центр",
    "description": "Языковой центр изучения английского языка для детей, подростков и взрослых.",
    "target_audience": "Дети, подростки, взрослые",
    "services": "Английский язык для детей, подростков и взрослых; разговорный английский; подготовка к ОГЭ/ЕГЭ",
    "brand_aliases": [
        "Priority Center",
        "Priority",
        "Priority Centre",
        "Приоритет",
        "Приоритет Центр",
    ],
    "competitors": [],  # DEMO: add real competitors manually in the Project UI
}

PROMPTS = [
    # discovery
    ("Какие хорошие языковые школы английского есть во Владивостоке?", "discovery", "commercial"),
    ("Какие языковые центры во Владивостоке стоит рассмотреть для изучения английского?", "discovery", "commercial"),
    ("Посоветуй несколько хороших школ английского во Владивостоке.", "discovery", "commercial"),
    ("Назови лучшие школы английского языка во Владивостоке для детей и взрослых.", "discovery", "commercial"),
    # children
    ("Куда во Владивостоке отдать ребёнка на английский?", "children", "commercial"),
    ("Какие языковые школы во Владивостоке хорошо подходят детям?", "children", "commercial"),
    ("Где во Владивостоке заниматься английским ребёнку 8 лет?", "children", "commercial"),
    ("Посоветуй языковой центр во Владивостоке для ребёнка 10 лет, который плохо знает английский.", "children", "commercial"),
    # teenagers
    ("Где подростку во Владивостоке заниматься английским языком?", "teenagers", "commercial"),
    ("Какие языковые школы во Владивостоке подходят подросткам?", "teenagers", "commercial"),
    ("Где во Владивостоке подготовиться к ОГЭ по английскому языку?", "teenagers", "commercial"),
    # adults
    ("Где взрослому человеку во Владивостоке выучить английский с нуля?", "adults", "commercial"),
    ("Какие курсы английского для взрослых во Владивостоке стоит рассмотреть?", "adults", "commercial"),
    ("Где во Владивостоке лучше заниматься разговорным английским?", "adults", "commercial"),
    # situation
    ("Я живу во Владивостоке, ребёнку 9 лет, английский в школе даётся плохо. Хочу найти хорошие дополнительные занятия. Какие варианты стоит рассмотреть?", "situation", "commercial"),
    ("Моей дочери 13 лет. Она знает грамматику, но практически не говорит по-английски. Что можно сделать и какие языковые центры во Владивостоке подойдут?", "situation", "commercial"),
    ("Мне 35 лет, английский почти с нуля. Хочу наконец начать нормально говорить для путешествий. Какие варианты обучения во Владивостоке посоветуешь?", "situation", "commercial"),
    # decision
    ("Сравни несколько языковых школ Владивостока и помоги выбрать лучшую для ребёнка 8–10 лет.", "decision", "commercial"),
    ("Какие языковые школы во Владивостоке считаются сильными именно в обучении детей и подростков?", "decision", "commercial"),
    ("Подбери 3–5 языковых центров во Владивостоке, которые стоит рассмотреть родителю, выбирающему английский для ребёнка.", "decision", "commercial"),
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # Ensure Default Organization exists (idempotent).
        org = (
            await db.execute(select(Organization).where(Organization.slug == "default"))
        ).scalar_one_or_none()
        if org is None:
            org = Organization(name="Default Organization", slug="default")
            db.add(org)
            await db.flush()
            logger.info("Created Default Organization")

        project = (
            await db.execute(select(Project).where(Project.name == PROJECT_DATA["name"]))
        ).scalar_one_or_none()

        if project is None:
            project = Project(organization_id=org.id, **PROJECT_DATA)
            db.add(project)
            await db.flush()
            logger.info("Created project: %s", project.name)
        else:
            # Ensure existing project is linked to an organization.
            if project.organization_id is None:
                project.organization_id = org.id
            logger.info("Project already exists: %s", project.name)

        existing_texts = set(
            (await db.execute(select(Prompt.text).where(Prompt.project_id == project.id))).scalars()
        )
        created = 0
        for text, cluster, intent in PROMPTS:
            if text in existing_texts:
                continue
            db.add(
                Prompt(
                    project_id=project.id,
                    text=text,
                    cluster=cluster,
                    intent=intent,
                    active=True,
                )
            )
            created += 1
        await db.commit()
        logger.info("Prompts created: %d (total for project: %d)", created, len(PROMPTS))

    print("Seed finished.")
    print("NOTE: seed data is DEMO data. Verify project website and add real competitors.")
    print("Project website is a demo value and should be confirmed before real research.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(seed())

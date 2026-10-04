from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_org_project, get_org_prompt
from app.auth import get_current_organization
from app.database import get_db
from app.models.organization import Organization
from app.models.prompt import Prompt
from app.schemas.prompt import PromptBulkImportResult, PromptCreate, PromptRead, PromptUpdate

router = APIRouter(prefix="/api", tags=["prompts"])


@router.get("/projects/{project_id}/prompts", response_model=list[PromptRead])
async def list_prompts(
    project_id: int,
    cluster: Optional[str] = Query(default=None),
    active: Optional[bool] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    await get_org_project(db, project_id, current_org.id)
    query = select(Prompt).where(Prompt.project_id == project_id).order_by(Prompt.id)
    if cluster:
        query = query.where(Prompt.cluster == cluster)
    if active is not None:
        query = query.where(Prompt.active.is_(active))
    return list((await db.execute(query)).scalars())


@router.post("/projects/{project_id}/prompts", response_model=PromptRead, status_code=201)
async def create_prompt(
    project_id: int,
    payload: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    await get_org_project(db, project_id, current_org.id)
    prompt = Prompt(project_id=project_id, **payload.model_dump())
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.put("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: int,
    payload: PromptUpdate,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    prompt = await get_org_prompt(db, prompt_id, current_org.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prompt, field, value)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete("/prompts/{prompt_id}", status_code=204)
async def delete_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    prompt = await get_org_prompt(db, prompt_id, current_org.id)
    await db.delete(prompt)
    await db.commit()


@router.post("/projects/{project_id}/prompts/import", response_model=PromptBulkImportResult)
async def import_prompts_csv(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    """CSV format: text,cluster,intent  (one header row optional)."""
    await get_org_project(db, project_id, current_org.id)
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    result = PromptBulkImportResult()
    if not rows:
        return result

    start = 1
    if rows and len(rows[0]) >= 1 and rows[0][0].strip().lower() == "text":
        start = 2

    for row in rows[start:]:
        if not row or not row[0].strip():
            result.skipped += 1
            continue
        text_val = row[0].strip()
        cluster_val = row[1].strip() if len(row) > 1 and row[1].strip() else None
        intent_val = row[2].strip() if len(row) > 2 and row[2].strip() else None
        existing = (
            await db.execute(
                select(Prompt).where(Prompt.project_id == project_id, Prompt.text == text_val)
            )
        ).scalar_one_or_none()
        if existing:
            result.skipped += 1
            continue
        db.add(Prompt(project_id=project_id, text=text_val, cluster=cluster_val, intent=intent_val))
        result.created += 1

    await db.commit()
    return result


@router.get("/projects/{project_id}/prompts/export")
async def export_prompts_csv(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_org: Organization = Depends(get_current_organization),
):
    await get_org_project(db, project_id, current_org.id)
    prompts = list(
        (await db.execute(select(Prompt).where(Prompt.project_id == project_id).order_by(Prompt.id))).scalars()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["text", "cluster", "intent"])
    for p in prompts:
        writer.writerow([p.text, p.cluster or "", p.intent or ""])
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="prompts_project_{project_id}.csv"'},
    )

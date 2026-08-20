from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models import PromptTemplate, User
from backend.app.services.prompt_templates_builtin import list_builtin_templates

router = APIRouter(prefix="/prompt-templates", tags=["prompt-templates"])


class PromptTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    category: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=256)
    topic_hint: str = Field(default="", max_length=2000)
    reference_hint: str = Field(default="", max_length=2000)
    instruction: str = Field(default="", max_length=2000)
    system_prompt: str = Field(default="", max_length=2000)


class PromptTemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    category: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=256)
    topic_hint: Optional[str] = Field(default=None, max_length=2000)
    reference_hint: Optional[str] = Field(default=None, max_length=2000)
    instruction: Optional[str] = Field(default=None, max_length=2000)
    system_prompt: Optional[str] = Field(default=None, max_length=2000)


def serialize_prompt_template(template: PromptTemplate) -> dict:
    return {
        "id": template.id,
        "is_builtin": False,
        "name": template.name,
        "category": template.category,
        "description": template.description,
        "topic_hint": template.topic_hint,
        "reference_hint": template.reference_hint,
        "instruction": template.instruction,
        "system_prompt": template.system_prompt,
    }


def _get_owned_template(db: Session, current_user: User, template_id: int) -> PromptTemplate:
    template = db.get(PromptTemplate, template_id)
    if template is None or template.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
    return template


def _ensure_unique_name(
    db: Session, current_user: User, name: str, exclude_id: Optional[int] = None
) -> None:
    statement = select(PromptTemplate).where(
        PromptTemplate.user_id == current_user.id, PromptTemplate.name == name
    )
    if exclude_id is not None:
        statement = statement.where(PromptTemplate.id != exclude_id)
    if db.scalars(statement).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name already exists")


@router.get("")
def list_prompt_templates(
    category: Optional[str] = Query(default=None, max_length=64),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List prompt templates available to the user: shipped built-ins + own custom."""
    custom_stmt = select(PromptTemplate).where(PromptTemplate.user_id == current_user.id)
    if category:
        custom_stmt = custom_stmt.where(PromptTemplate.category == category)
    custom = [serialize_prompt_template(t) for t in db.scalars(custom_stmt.order_by(PromptTemplate.id.desc())).all()]

    items = list_builtin_templates(category) + custom
    return {"total": len(items), "page": 1, "page_size": len(items) or 1, "items": items}


@router.post("")
def create_prompt_template(
    payload: PromptTemplateCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    _ensure_unique_name(db, current_user, name)
    template = PromptTemplate(
        user_id=current_user.id,
        name=name,
        category=payload.category,
        description=payload.description,
        topic_hint=payload.topic_hint,
        reference_hint=payload.reference_hint,
        instruction=payload.instruction,
        system_prompt=payload.system_prompt,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return serialize_prompt_template(template)


@router.patch("/{template_id}")
def update_prompt_template(
    template_id: int,
    payload: PromptTemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = _get_owned_template(db, current_user, template_id)
    if payload.name is not None:
        new_name = payload.name.strip()
        _ensure_unique_name(db, current_user, new_name, exclude_id=template.id)
        template.name = new_name
    for field in ("category", "description", "topic_hint", "reference_hint", "instruction", "system_prompt"):
        value = getattr(payload, field)
        if value is not None:
            setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return serialize_prompt_template(template)


@router.delete("/{template_id}")
def delete_prompt_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = _get_owned_template(db, current_user, template_id)
    db.delete(template)
    db.commit()
    return {"status": "deleted", "id": template_id}

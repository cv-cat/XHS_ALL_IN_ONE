from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import encrypt_text
from backend.app.models import DEFAULT_TEXT_MODEL_NAME, ModelConfig, User
from backend.app.schemas.common import paginated

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


class ModelConfigCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    model_type: str = Field(pattern="^(text|image)$")
    provider: str = Field(min_length=1, max_length=64)
    model_name: str = Field(default="", max_length=128)
    base_url: str = ""
    api_key: str = ""
    is_default: bool = False


class ModelConfigUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    provider: Optional[str] = Field(default=None, min_length=1, max_length=64)
    model_name: Optional[str] = Field(default=None, max_length=128)
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_default: Optional[bool] = None


def _serialize_config(config: ModelConfig) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "model_type": config.model_type,
        "provider": config.provider,
        "model_name": config.model_name,
        "base_url": config.base_url,
        "has_api_key": bool(config.encrypted_api_key),
        "is_default": config.is_default,
    }


def _default_model_name(model_type: str) -> str:
    return DEFAULT_TEXT_MODEL_NAME if model_type == "text" else ""


def _normalize_model_name(model_type: str, model_name: Optional[str]) -> str:
    if model_name == "gpt5.4":
        return DEFAULT_TEXT_MODEL_NAME
    cleaned = (model_name or "").strip()
    return cleaned or _default_model_name(model_type)


def _get_owned_config(db: Session, current_user: User, config_id: int) -> ModelConfig:
    config = db.get(ModelConfig, config_id)
    if config is None or config.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found")
    return config


def _clear_default_for_type(db: Session, user_id: int, model_type: str) -> None:
    configs = db.scalars(
        select(ModelConfig).where(ModelConfig.user_id == user_id, ModelConfig.model_type == model_type)
    ).all()
    for config in configs:
        config.is_default = False


@router.get("")
def get_model_configs(
    model_type: Optional[str] = Query(default=None, pattern="^(text|image)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(ModelConfig).where(ModelConfig.user_id == current_user.id)
    if model_type:
        statement = statement.where(ModelConfig.model_type == model_type)
    configs = db.scalars(statement.order_by(ModelConfig.id.desc())).all()
    return paginated([_serialize_config(config) for config in configs], page, page_size)


@router.post("")
def create_model_config(
    payload: ModelConfigCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.is_default:
        _clear_default_for_type(db, current_user.id, payload.model_type)

    config = ModelConfig(
        user_id=current_user.id,
        name=payload.name,
        model_type=payload.model_type,
        provider=payload.provider,
        model_name=_normalize_model_name(payload.model_type, payload.model_name),
        base_url=payload.base_url,
        encrypted_api_key=encrypt_text(payload.api_key) if payload.api_key else "",
        is_default=payload.is_default,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return _serialize_config(config)


@router.post("/{config_id}/test")
def test_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.security import decrypt_text

    config = _get_owned_config(db, current_user, config_id)
    if not config.encrypted_api_key:
        return {"id": config.id, "status": "error", "message": "未配置 API Key"}
    if not config.base_url:
        return {"id": config.id, "status": "error", "message": "未配置 Base URL"}

    api_key = decrypt_text(config.encrypted_api_key)
    base_url = config.base_url.rstrip("/")

    try:
        import requests as http_requests

        if config.model_type == "image":
            resp = http_requests.post(
                f"{base_url}/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": config.model_name, "prompt": "test", "n": 1, "size": "256x256"},
                timeout=15,
            )
        else:
            resp = http_requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": config.model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
                timeout=15,
            )

        if resp.status_code < 400:
            try:
                body = resp.json()
                if body.get("choices") or body.get("data") or body.get("object"):
                    return {"id": config.id, "status": "ok", "message": f"连接成功 ({resp.status_code})"}
                return {"id": config.id, "status": "error", "message": f"响应格式异常: {resp.text[:150]}"}
            except Exception:
                return {"id": config.id, "status": "error", "message": f"响应非 JSON: {resp.text[:150]}"}
        else:
            return {"id": config.id, "status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:150]}"}
    except Exception as exc:
        return {"id": config.id, "status": "error", "message": str(exc)[:200]}


@router.patch("/{config_id}")
def update_model_config(
    config_id: int,
    payload: ModelConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_owned_config(db, current_user, config_id)

    if payload.name is not None:
        config.name = payload.name
    if payload.provider is not None:
        config.provider = payload.provider
    if payload.model_name is not None:
        config.model_name = _normalize_model_name(config.model_type, payload.model_name)
    if payload.base_url is not None:
        config.base_url = payload.base_url
    if payload.api_key is not None:
        config.encrypted_api_key = encrypt_text(payload.api_key) if payload.api_key else ""
    if payload.is_default is not None:
        if payload.is_default:
            _clear_default_for_type(db, current_user.id, config.model_type)
        config.is_default = payload.is_default

    db.commit()
    db.refresh(config)
    return _serialize_config(config)


@router.delete("/{config_id}")
def delete_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_owned_config(db, current_user, config_id)
    db.delete(config)
    db.commit()
    return {"id": config_id, "status": "deleted"}


@router.post("/{config_id}/set-default")
def set_default_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_owned_config(db, current_user, config_id)
    _clear_default_for_type(db, current_user.id, config.model_type)
    config.is_default = True
    db.commit()
    db.refresh(config)
    return _serialize_config(config)

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.app.core.deps import get_current_user
from backend.app.models import User
from backend.app.schemas.common import paginated
from backend.app.services.prompt_templates_builtin import list_builtin_templates

router = APIRouter(prefix="/prompt-templates", tags=["prompt-templates"])


@router.get("")
def list_prompt_templates(
    category: Optional[str] = Query(default=None, max_length=64),
    current_user: User = Depends(get_current_user),
):
    """List prompt templates available to the user.

    Currently returns the shipped built-in templates. User-custom templates
    (DB-backed) will be merged in here in a later iteration.
    """
    items = list_builtin_templates(category)
    return paginated(items, page=1, page_size=max(len(items), 1))

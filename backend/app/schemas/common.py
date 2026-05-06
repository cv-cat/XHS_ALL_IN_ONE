from __future__ import annotations

from typing import Any, Iterable


def paginated(items: Iterable[Any], page: int = 1, page_size: int = 20) -> dict:
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 100)
    materialized = list(items)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "total": len(materialized),
        "page": safe_page,
        "page_size": safe_page_size,
        "items": materialized[start:end],
    }

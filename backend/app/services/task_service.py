from __future__ import annotations

from typing import Optional

from backend.app.services.mock_data import sample_tasks


def list_tasks(platform: Optional[str] = None) -> list[dict]:
    tasks = sample_tasks()
    if platform:
        return [task for task in tasks if task["platform"] == platform]
    return tasks

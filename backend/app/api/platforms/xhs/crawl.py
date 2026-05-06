from __future__ import annotations

import json
import time
from typing import Any, Generator, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.api.platforms.xhs.pc import (
    _get_owned_pc_account_cookies,
    _normalize_detail_payload,
    _normalize_search_item,
    normalize_comment_payload,
    get_xhs_pc_api_adapter_factory,
)
from backend.app.api.tasks import serialize_task
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models import Note, NoteAsset, PlatformAccount, Task, User

router = APIRouter(prefix="/xhs/crawl", tags=["xhs-crawl"])


class CrawlSearchNotesRequest(BaseModel):
    account_id: int
    keyword: str = Field(min_length=1, max_length=120)
    page: int = Field(default=1, ge=1)
    save_to_library: bool = True
    fetch_comments: bool = False


class CrawlNoteUrlsRequest(BaseModel):
    account_id: int
    urls: list[str] = Field(min_length=1, max_length=50)
    save_to_library: bool = True
    fetch_comments: bool = False


class CrawlUserNotesRequest(BaseModel):
    account_id: int
    user_url: str = Field(min_length=1)
    save_to_library: bool = True


class DataCrawlRequest(BaseModel):
    account_id: int
    mode: Literal["note_urls", "search", "comments"]
    urls: list[str] = Field(default_factory=list, max_length=100)
    keyword: str = Field(default="", max_length=120)
    pages: int = Field(default=1, ge=1, le=20)
    max_notes: int = Field(default=20, ge=1, le=200)
    time_sleep: float = Field(default=0, ge=0, le=60)
    fetch_comments: bool = False
    sort_type_choice: int = Field(default=0, ge=0, le=4)
    note_type: int = Field(default=0, ge=0, le=2)
    note_time: int = Field(default=0, ge=0, le=3)
    note_range: int = Field(default=0, ge=0, le=3)
    pos_distance: int = Field(default=0, ge=0, le=2)
    geo: str = ""


def _serialize_note(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "platform": note.platform,
        "platform_account_id": note.platform_account_id,
        "note_id": note.note_id,
        "title": note.title,
        "content": note.content,
        "author_name": note.author_name,
        "raw_json": note.raw_json,
        "created_at": note.created_at.isoformat(),
    }


def _create_crawl_task(
    db: Session,
    current_user: User,
    crawl_type: str,
    payload: dict[str, Any],
) -> Task:
    task = Task(
        user_id=current_user.id,
        platform="xhs",
        task_type="crawl",
        status="running",
        progress=10,
        payload={"crawl_type": crawl_type, **payload},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _complete_task(db: Session, task: Task, payload: dict[str, Any]) -> Task:
    task.status = "completed"
    task.progress = 100
    task.payload = {**(task.payload or {}), **payload}
    db.commit()
    db.refresh(task)
    return task


def _fail_task(db: Session, task: Task, error: str) -> None:
    task.status = "failed"
    task.progress = 100
    task.payload = {**(task.payload or {}), "error": error}
    db.commit()


def _data_items(raw_payload: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_payload, dict):
        return []
    data = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else raw_payload
    items = data.get("items") or data.get("notes") or data.get("list") or []
    return [item for item in items if isinstance(item, dict) and item.get("model_type") not in ("rec_query", "hot_query")]


def _raw_with_metrics(normalized: dict[str, Any]) -> dict[str, Any]:
    raw = normalized.get("raw") if isinstance(normalized.get("raw"), dict) else {}
    return {
        **raw,
        "note_url": normalized.get("note_url", ""),
        "tags": normalized.get("tags", []),
        "likes": normalized.get("likes", 0),
        "collects": normalized.get("collects", 0),
        "comments": normalized.get("comments", 0),
        "shares": normalized.get("shares", 0),
    }


def _image_urls(normalized: dict[str, Any]) -> list[str]:
    urls = normalized.get("image_urls")
    if isinstance(urls, list) and urls:
        return [str(url) for url in urls if url]
    cover_url = normalized.get("cover_url")
    return [str(cover_url)] if cover_url else []


def _video_url(normalized: dict[str, Any]) -> str:
    return str(normalized.get("video_url") or normalized.get("video_addr") or "")


def _save_normalized_notes(
    db: Session,
    account: PlatformAccount,
    normalized_items: list[dict[str, Any]],
) -> list[Note]:
    saved: list[Note] = []
    for normalized in normalized_items:
        note_id = str(normalized.get("note_id") or "").strip()
        if not note_id:
            continue
        note = db.scalars(
            select(Note).where(Note.user_id == account.user_id, Note.note_id == note_id)
        ).first()
        if note is None:
            note = Note(user_id=account.user_id, platform_account_id=account.id, platform=account.platform, note_id=note_id)
            db.add(note)
        note.title = str(normalized.get("title") or "")
        note.content = str(normalized.get("content") or "")
        note.author_name = str(normalized.get("author_name") or "")
        note.raw_json = _raw_with_metrics(normalized)
        db.flush()
        db.execute(delete(NoteAsset).where(NoteAsset.note_id == note.id))
        for url in _image_urls(normalized):
            local_name = _download_asset(url, account.user_id, "image")
            db.add(NoteAsset(note_id=note.id, asset_type="image", url=url, local_path=local_name or ""))
        video_url = _video_url(normalized)
        if video_url:
            local_name = _download_asset(video_url, account.user_id, "video")
            db.add(NoteAsset(note_id=note.id, asset_type="video", url=video_url, local_path=local_name or ""))
        saved.append(note)

    db.commit()
    for note in saved:
        db.refresh(note)
    return saved


def _download_asset(url: str, user_id: int, asset_type: str) -> str | None:
    from backend.app.services.asset_downloader import download_asset_to_local
    return download_asset_to_local(url, user_id, asset_type)


def _sleep_between_requests(seconds: float) -> None:
    if seconds > 0:
        time.sleep(min(seconds, 60))


def _crawl_data_item(
    *,
    source: str,
    status: str,
    note: dict[str, Any] | None = None,
    comments: list[dict[str, Any]] | None = None,
    error: str = "",
) -> dict[str, Any]:
    return {
        "source": source,
        "status": status,
        "error": error,
        "note": note,
        "comments": comments or [],
        "comment_count": len(comments or []),
    }


def _owned_pc_account(db: Session, current_user: User, account_id: int) -> PlatformAccount:
    account = db.get(PlatformAccount, account_id)
    if (
        account is None
        or account.user_id != current_user.id
        or account.platform != "xhs"
        or account.sub_type != "pc"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.post("/search-notes")
def crawl_search_notes(
    payload: CrawlSearchNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    account = _owned_pc_account(db, current_user, payload.account_id)
    cookies = _get_owned_pc_account_cookies(db, current_user, payload.account_id)
    task = _create_crawl_task(
        db,
        current_user,
        "search_notes",
        {"account_id": account.id, "keyword": payload.keyword, "page": payload.page},
    )
    success, message, raw_payload = adapter_factory(cookies).search_note(payload.keyword, page=payload.page)
    if not success:
        _fail_task(db, task, message or "XHS search crawl failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message or "XHS search crawl failed")

    normalized_items = [_normalize_search_item(item) for item in _data_items(raw_payload)]
    saved_notes = _save_normalized_notes(db, account, normalized_items) if payload.save_to_library else []
    task = _complete_task(
        db,
        task,
        {"result_count": len(normalized_items), "saved_count": len(saved_notes)},
    )
    return {
        "task": serialize_task(task),
        "result_count": len(normalized_items),
        "saved_count": len(saved_notes),
        "items": [_serialize_note(note) for note in saved_notes],
        "raw": raw_payload,
    }


@router.post("/note-urls")
def crawl_note_urls(
    payload: CrawlNoteUrlsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    account = _owned_pc_account(db, current_user, payload.account_id)
    cookies = _get_owned_pc_account_cookies(db, current_user, payload.account_id)
    task = _create_crawl_task(
        db,
        current_user,
        "note_urls",
        {"account_id": account.id, "url_count": len(payload.urls)},
    )
    adapter = adapter_factory(cookies)
    normalized_items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for url in payload.urls:
        success, message, raw_payload = adapter.get_note_info(url)
        if success:
            normalized_items.append(_normalize_detail_payload(raw_payload or {}))
        else:
            errors.append({"url": url, "error": message or "XHS note detail crawl failed"})

    saved_notes = _save_normalized_notes(db, account, normalized_items) if payload.save_to_library else []
    task = _complete_task(
        db,
        task,
        {"result_count": len(normalized_items), "saved_count": len(saved_notes), "errors": errors},
    )
    return {
        "task": serialize_task(task),
        "result_count": len(normalized_items),
        "saved_count": len(saved_notes),
        "errors": errors,
        "items": [_serialize_note(note) for note in saved_notes],
    }


@router.post("/user-notes")
def crawl_user_notes(
    payload: CrawlUserNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    account = _owned_pc_account(db, current_user, payload.account_id)
    cookies = _get_owned_pc_account_cookies(db, current_user, payload.account_id)
    task = _create_crawl_task(
        db,
        current_user,
        "user_notes",
        {"account_id": account.id, "user_url": payload.user_url},
    )
    success, message, raw_payload = adapter_factory(cookies).get_user_notes(payload.user_url)
    if not success:
        _fail_task(db, task, message or "XHS user notes crawl failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message or "XHS user notes crawl failed")

    normalized_items = [_normalize_search_item(item) for item in _data_items(raw_payload)]
    saved_notes = _save_normalized_notes(db, account, normalized_items) if payload.save_to_library else []
    task = _complete_task(
        db,
        task,
        {"result_count": len(normalized_items), "saved_count": len(saved_notes)},
    )
    return {
        "task": serialize_task(task),
        "result_count": len(normalized_items),
        "saved_count": len(saved_notes),
        "items": [_serialize_note(note) for note in saved_notes],
        "raw": raw_payload,
    }


def _sse_event(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/data")
def crawl_data(
    payload: DataCrawlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    account = _owned_pc_account(db, current_user, payload.account_id)
    cookies = _get_owned_pc_account_cookies(db, current_user, payload.account_id)
    task = _create_crawl_task(
        db,
        current_user,
        f"data_{payload.mode}",
        {
            "account_id": account.id,
            "mode": payload.mode,
            "keyword": payload.keyword,
            "url_count": len(payload.urls),
            "pages": payload.pages,
            "time_sleep": payload.time_sleep,
        },
    )
    task_id = task.id
    adapter = adapter_factory(cookies)

    def generate() -> Generator[str, None, None]:
        items: list[dict[str, Any]] = []
        normalized_for_save: list[dict[str, Any]] = []
        error_occurred = False

        try:
            if payload.mode == "note_urls":
                for index, url in enumerate(payload.urls):
                    success, message, raw_payload = adapter.get_note_info(url)
                    if success:
                        note = _normalize_detail_payload(raw_payload or {})
                        note["note_url"] = note.get("note_url") or url
                        normalized_for_save.append(note)
                        comments_list: list[dict[str, Any]] = []
                        if payload.fetch_comments:
                            cs, cm, cp = adapter.get_note_comments(url)
                            if cs:
                                comments_list = normalize_comment_payload(cp)
                            else:
                                item = _crawl_data_item(source=url, status="failed", note=note, error=cm or "comment crawl failed")
                                items.append(item)
                                yield _sse_event({"type": "item", "index": len(items) - 1, "item": item})
                                _sleep_between_requests(payload.time_sleep)
                                continue
                        item = _crawl_data_item(source=url, status="success", note=note, comments=comments_list)
                    else:
                        item = _crawl_data_item(source=url, status="failed", error=message or "detail crawl failed")
                    items.append(item)
                    yield _sse_event({"type": "item", "index": len(items) - 1, "item": item})
                    if index < len(payload.urls) - 1:
                        _sleep_between_requests(payload.time_sleep)

            elif payload.mode == "comments":
                for index, url in enumerate(payload.urls):
                    success, message, raw_payload = adapter.get_note_comments(url)
                    if success:
                        item = _crawl_data_item(source=url, status="success", comments=normalize_comment_payload(raw_payload))
                    else:
                        item = _crawl_data_item(source=url, status="failed", error=message or "comment crawl failed")
                    items.append(item)
                    yield _sse_event({"type": "item", "index": len(items) - 1, "item": item})
                    if index < len(payload.urls) - 1:
                        _sleep_between_requests(payload.time_sleep)

            else:
                if not payload.keyword.strip():
                    yield _sse_event({"type": "error", "message": "Keyword is required"})
                    return
                seen_urls: list[str] = []
                for page in range(1, payload.pages + 1):
                    success, message, raw_payload = adapter.search_note(
                        payload.keyword, page=page,
                        sort_type_choice=payload.sort_type_choice,
                        note_type=payload.note_type,
                        note_time=payload.note_time,
                        note_range=payload.note_range,
                        pos_distance=payload.pos_distance,
                        geo=payload.geo,
                    )
                    if not success:
                        item = _crawl_data_item(source=f"page:{page}", status="failed", error=message or "search failed")
                        items.append(item)
                        yield _sse_event({"type": "item", "index": len(items) - 1, "item": item})
                        break
                    yield _sse_event({"type": "progress", "message": f"搜索第 {page} 页完成，开始获取详情..."})
                    for raw_item in _data_items(raw_payload):
                        if len(items) >= payload.max_notes:
                            break
                        search_note = _normalize_search_item(raw_item)
                        note_url = search_note.get("note_url") or ""
                        source = note_url or str(search_note.get("note_id") or f"page:{page}")
                        if source in seen_urls:
                            continue
                        seen_urls.append(source)
                        detail_note = search_note
                        if note_url:
                            ds, dm, dp = adapter.get_note_info(note_url)
                            if ds:
                                detail_note = _normalize_detail_payload(dp or {}, source_url=note_url)
                                detail_note["note_url"] = detail_note.get("note_url") or note_url
                            else:
                                item = _crawl_data_item(source=source, status="failed", note=search_note, error=dm or "detail failed")
                                items.append(item)
                                yield _sse_event({"type": "item", "index": len(items) - 1, "item": item})
                                _sleep_between_requests(payload.time_sleep)
                                continue
                        comments_list = []
                        if payload.fetch_comments and note_url:
                            cs, cm, cp = adapter.get_note_comments(note_url)
                            if cs:
                                comments_list = normalize_comment_payload(cp)
                            else:
                                item = _crawl_data_item(source=source, status="failed", note=detail_note, error=cm or "comment failed")
                                items.append(item)
                                yield _sse_event({"type": "item", "index": len(items) - 1, "item": item})
                                _sleep_between_requests(payload.time_sleep)
                                continue
                        normalized_for_save.append(detail_note)
                        item = _crawl_data_item(source=source, status="success", note=detail_note, comments=comments_list)
                        items.append(item)
                        yield _sse_event({"type": "item", "index": len(items) - 1, "item": item})
                        _sleep_between_requests(payload.time_sleep)
                    if len(items) >= payload.max_notes:
                        break
                    data = (raw_payload or {}).get("data") or {}
                    if not data.get("has_more", False):
                        break

        except Exception as exc:
            error_occurred = True
            yield _sse_event({"type": "error", "message": str(exc)})

        success_count = len([i for i in items if i["status"] == "success"])
        failed_count = len(items) - success_count
        try:
            if error_occurred:
                _fail_task(db, task, "partial failure")
            else:
                _complete_task(db, task, {"result_count": success_count, "failed_count": failed_count})
        except Exception:
            pass

        yield _sse_event({
            "type": "done",
            "task_id": task_id,
            "total": len(items),
            "success_count": success_count,
            "failed_count": failed_count,
        })

    return StreamingResponse(generate(), media_type="text/event-stream")

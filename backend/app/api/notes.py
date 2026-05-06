from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from backend.app.api.platforms.xhs.pc import (
    _cookies_to_string,
    get_xhs_pc_api_adapter_factory,
    normalize_comment_payload,
)
from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.time import shanghai_now
from backend.app.core.security import decrypt_text
from backend.app.models import AccountCookieVersion, AiDraft, Note, NoteAsset, NoteComment, PlatformAccount, Tag, User, note_tags
from backend.app.schemas.common import paginated

router = APIRouter(prefix="/notes", tags=["notes"])


class BatchSaveNoteItem(BaseModel):
    note_id: str = Field(min_length=1, max_length=128)
    note_url: str = ""
    title: str = ""
    content: str = ""
    author_name: str = ""
    cover_url: str = ""
    video_url: str = ""
    video_addr: str = ""
    image_urls: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class BatchSaveNotesRequest(BaseModel):
    account_id: int
    fetch_comments: bool = False
    notes: list[BatchSaveNoteItem] = Field(min_length=1)


class BatchTagNotesRequest(BaseModel):
    note_ids: list[int] = Field(min_length=1)
    tag_ids: list[int] = Field(default_factory=list)
    mode: Literal["replace", "add", "remove"] = "replace"


class BatchCreateDraftsRequest(BaseModel):
    note_ids: list[int] = Field(min_length=1)
    intent: str = Field(default="rewrite", max_length=32)


class ExportNotesRequest(BaseModel):
    note_ids: list[int] = Field(min_length=1)
    format: Literal["json", "csv"] = "json"


def _serialize_tag(tag: Tag) -> dict:
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
    }


def _get_note_tags(db: Session, note_id: int) -> list[dict]:
    tags = db.scalars(
        select(Tag)
        .join(note_tags, Tag.id == note_tags.c.tag_id)
        .where(note_tags.c.note_id == note_id)
        .order_by(Tag.id.asc())
    ).all()
    return [_serialize_tag(tag) for tag in tags]


def _get_note_assets(db: Session, note: Note) -> list[NoteAsset]:
    return db.scalars(select(NoteAsset).where(NoteAsset.note_id == note.id).order_by(NoteAsset.sort_order.asc(), NoteAsset.id.asc())).all()


def _asset_display_url(asset: NoteAsset) -> str:
    if asset.local_path:
        return f"/api/files/media/{asset.local_path}"
    return asset.url


def _serialize_note(db: Session, note: Note) -> dict:
    assets = _get_note_assets(db, note)
    image_assets = [asset for asset in assets if asset.asset_type == "image"]
    video_assets = [asset for asset in assets if asset.asset_type == "video"]
    asset_urls = [_asset_display_url(asset) for asset in assets if asset.url or asset.local_path]
    raw = note.raw_json if isinstance(note.raw_json, dict) else {}
    raw_cover = raw.get("cover_url") if isinstance(raw.get("cover_url"), str) else ""
    return {
        "id": note.id,
        "platform": note.platform,
        "platform_account_id": note.platform_account_id,
        "note_id": note.note_id,
        "title": note.title,
        "content": note.content,
        "author_name": note.author_name,
        "raw_json": note.raw_json,
        "asset_urls": asset_urls,
        "cover_url": _asset_display_url(image_assets[0]) if image_assets else raw_cover,
        "video_url": _asset_display_url(video_assets[0]) if video_assets else "",
        "video_addr": _asset_display_url(video_assets[0]) if video_assets else "",
        "created_at": note.created_at.isoformat(),
    }


def _serialize_note_with_tags(db: Session, note: Note) -> dict:
    serialized = _serialize_note(db, note)
    serialized["tags"] = _get_note_tags(db, note.id)
    return serialized


def _build_notes_csv(db: Session, notes: list[Note]) -> str:
    output = io.StringIO()
    fieldnames = ["note_id", "title", "author_name", "content", "tags", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for note in notes:
        tags = ",".join(tag["name"] for tag in _get_note_tags(db, note.id))
        writer.writerow(
            {
                "note_id": note.note_id,
                "title": note.title,
                "author_name": note.author_name,
                "content": note.content,
                "tags": tags,
                "created_at": note.created_at.isoformat(),
            }
        )
    return output.getvalue()


def _serialize_asset(asset: NoteAsset) -> dict:
    return {
        "id": asset.id,
        "note_id": asset.note_id,
        "asset_type": asset.asset_type,
        "url": _asset_display_url(asset),
        "local_path": asset.local_path,
        "download_url": f"/api/files/media/{asset.local_path}" if asset.local_path else "",
        "sort_order": asset.sort_order,
    }


def _serialize_comment(comment: NoteComment) -> dict:
    return {
        "id": comment.id,
        "note_id": comment.note_id,
        "comment_id": comment.comment_id,
        "user_name": comment.user_name,
        "user_id": comment.user_id,
        "content": comment.content,
        "like_count": comment.like_count,
        "parent_comment_id": comment.parent_comment_id,
        "created_at_remote": comment.created_at_remote,
        "raw_json": comment.raw_json,
    }


def _serialize_draft(draft: AiDraft) -> dict:
    return {
        "id": draft.id,
        "platform": draft.platform,
        "title": draft.title,
        "body": draft.body,
        "source_note_id": draft.source_note_id,
        "created_at": draft.created_at.isoformat(),
    }


def _get_owned_account(db: Session, current_user: User, account_id: int) -> PlatformAccount:
    account = db.get(PlatformAccount, account_id)
    if account is None or account.user_id != current_user.id or account.platform != "xhs":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def _get_latest_account_cookies(db: Session, account: PlatformAccount) -> str:
    cookie_version = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account.id)
        .order_by(AccountCookieVersion.created_at.desc())
    ).first()
    if cookie_version is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account has no cookies")
    return _cookies_to_string(decrypt_text(cookie_version.encrypted_cookies))


def _get_owned_note(db: Session, current_user: User, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None or note.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _get_unique_owned_notes(db: Session, current_user: User, note_ids: list[int]) -> list[Note]:
    return [_get_owned_note(db, current_user, note_id) for note_id in dict.fromkeys(note_ids)]


@router.get("/ids")
def get_note_ids(
    platform: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = (
        select(Note.note_id)
        .where(Note.user_id == current_user.id)
    )
    if platform:
        statement = statement.where(Note.platform == platform)
    note_ids = db.scalars(statement).all()
    return {"items": list(note_ids)}


@router.get("")
def get_notes(
    platform: Optional[str] = None,
    q: Optional[str] = None,
    tag_id: Optional[int] = None,
    has_assets: Optional[bool] = None,
    has_comments: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = (
        select(Note)
        .where(Note.user_id == current_user.id)
    )
    if platform:
        statement = statement.where(Note.platform == platform)
    if q:
        keyword = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Note.title.ilike(keyword),
                Note.content.ilike(keyword),
                Note.author_name.ilike(keyword),
                Note.note_id.ilike(keyword),
            )
        )
    if tag_id is not None:
        tag = db.get(Tag, tag_id)
        if tag is None or tag.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        statement = statement.where(Note.id.in_(select(note_tags.c.note_id).where(note_tags.c.tag_id == tag_id)))
    if has_assets is True:
        statement = statement.where(Note.id.in_(select(NoteAsset.note_id)))
    elif has_assets is False:
        statement = statement.where(Note.id.not_in(select(NoteAsset.note_id)))
    if has_comments is True:
        statement = statement.where(Note.id.in_(select(NoteComment.note_id)))
    elif has_comments is False:
        statement = statement.where(Note.id.not_in(select(NoteComment.note_id)))
    notes = db.scalars(statement.order_by(Note.created_at.desc())).all()
    return paginated([_serialize_note_with_tags(db, note) for note in notes], page, page_size)


@router.post("/batch-create-drafts")
def batch_create_drafts(
    payload: BatchCreateDraftsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = _get_unique_owned_notes(db, current_user, payload.note_ids)
    drafts: list[AiDraft] = []
    for note in notes:
        draft = AiDraft(
            user_id=current_user.id,
            platform=note.platform,
            title=note.title,
            body=note.content,
            source_note_id=note.id,
        )
        db.add(draft)
        drafts.append(draft)

    db.commit()
    for draft in drafts:
        db.refresh(draft)

    return {
        "created_count": len(drafts),
        "items": [_serialize_draft(draft) for draft in drafts],
    }


@router.get("/{note_id}")
def get_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_note_with_tags(db, _get_owned_note(db, current_user, note_id))


@router.delete("/{note_id}")
def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, current_user, note_id)
    db.execute(delete(note_tags).where(note_tags.c.note_id == note.id))
    db.execute(delete(NoteAsset).where(NoteAsset.note_id == note.id))
    db.execute(delete(NoteComment).where(NoteComment.note_id == note.id))
    db.query(AiDraft).filter(AiDraft.source_note_id == note.id).update({"source_note_id": None})
    db.delete(note)
    db.commit()
    return {"id": note_id, "status": "deleted"}


@router.get("/{note_id}/assets")
def get_note_assets(
    note_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, current_user, note_id)
    assets = db.scalars(select(NoteAsset).where(NoteAsset.note_id == note.id).order_by(NoteAsset.sort_order.asc(), NoteAsset.id.asc())).all()
    return paginated([_serialize_asset(asset) for asset in assets], page, page_size)


class AddNoteAssetRequest(BaseModel):
    asset_type: str = Field(pattern="^(image|video)$")
    url: str = Field(default="", max_length=2048)
    local_path: str = Field(default="", max_length=512)


@router.post("/{note_id}/assets")
def add_note_asset(
    note_id: int,
    payload: AddNoteAssetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, current_user, note_id)
    if not payload.url and not payload.local_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url or local_path is required")
    asset = NoteAsset(
        note_id=note.id,
        asset_type=payload.asset_type,
        url=payload.url,
        local_path=payload.local_path,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _serialize_asset(asset)


@router.delete("/{note_id}/assets/{asset_id}")
def delete_note_asset(
    note_id: int,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, current_user, note_id)
    asset = db.scalars(
        select(NoteAsset).where(NoteAsset.id == asset_id, NoteAsset.note_id == note.id)
    ).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    db.delete(asset)
    db.commit()
    return {"id": asset_id, "status": "deleted"}


class ReorderAssetsRequest(BaseModel):
    asset_ids: list[int] = Field(min_length=1)


@router.put("/{note_id}/assets/reorder")
def reorder_note_assets(
    note_id: int,
    payload: ReorderAssetsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, current_user, note_id)
    assets = db.scalars(select(NoteAsset).where(NoteAsset.note_id == note.id)).all()
    asset_map = {a.id: a for a in assets}
    for idx, aid in enumerate(payload.asset_ids):
        if aid in asset_map:
            asset_map[aid].sort_order = idx
    db.commit()
    return {"ok": True}


@router.get("/{note_id}/comments")
def get_note_comments(
    note_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, current_user, note_id)
    comments = db.scalars(
        select(NoteComment).where(NoteComment.note_id == note.id).order_by(NoteComment.id.asc())
    ).all()
    return paginated([_serialize_comment(comment) for comment in comments], page, page_size)


def _download_asset(url: str, user_id: int, asset_type: str) -> str | None:
    from backend.app.services.asset_downloader import download_asset_to_local
    return download_asset_to_local(url, user_id, asset_type)


@router.post("/batch-save")
def batch_save_notes(
    payload: BatchSaveNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    account = _get_owned_account(db, current_user, payload.account_id)
    comment_adapter = None
    if payload.fetch_comments:
        if account.sub_type != "pc":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PC account is required to fetch comments")
        comment_adapter = adapter_factory(_get_latest_account_cookies(db, account))
    saved_notes: list[Note] = []

    for note_payload in payload.notes:
        existing = db.scalars(
            select(Note).where(
                Note.user_id == current_user.id,
                Note.note_id == note_payload.note_id,
            )
        ).first()
        if existing is None:
            existing = Note(
                user_id=current_user.id,
                platform_account_id=account.id,
                platform=account.platform,
                note_id=note_payload.note_id,
            )
            db.add(existing)

        existing.title = note_payload.title
        existing.content = note_payload.content
        existing.author_name = note_payload.author_name
        merged_raw = dict(note_payload.raw) if note_payload.raw else {}
        if note_payload.note_url:
            merged_raw["note_url"] = note_payload.note_url
        existing.raw_json = merged_raw
        db.flush()
        db.execute(delete(NoteAsset).where(NoteAsset.note_id == existing.id))
        image_candidates = [*note_payload.image_urls] or ([note_payload.cover_url] if note_payload.cover_url else [])
        unique_image_urls = [url for index, url in enumerate(image_candidates) if url and url not in image_candidates[:index]]
        for image_url in unique_image_urls:
            local_name = _download_asset(image_url, current_user.id, "image")
            db.add(NoteAsset(note_id=existing.id, asset_type="image", url=image_url, local_path=local_name or ""))
        video_url = note_payload.video_url or note_payload.video_addr
        if video_url:
            local_name = _download_asset(video_url, current_user.id, "video")
            db.add(NoteAsset(note_id=existing.id, asset_type="video", url=video_url, local_path=local_name or ""))
        if payload.fetch_comments and note_payload.note_url and comment_adapter is not None:
            success, message, raw_payload = comment_adapter.get_note_comments(note_payload.note_url)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=message or "XHS note comments failed",
                )
            db.execute(delete(NoteComment).where(NoteComment.note_id == existing.id))
            for comment in normalize_comment_payload(raw_payload):
                db.add(
                    NoteComment(
                        note_id=existing.id,
                        comment_id=comment["comment_id"],
                        user_name=comment["user_name"],
                        user_id=comment["user_id"],
                        content=comment["content"],
                        like_count=comment["like_count"],
                        parent_comment_id=comment["parent_comment_id"],
                        created_at_remote=comment["created_at_remote"],
                        raw_json=comment["raw_json"],
                    )
                )
        saved_notes.append(existing)

    db.commit()
    for note in saved_notes:
        db.refresh(note)

    return {
        "saved_count": len(saved_notes),
        "items": [_serialize_note_with_tags(db, note) for note in saved_notes],
    }


@router.post("/batch-tag")
def batch_tag_notes(
    payload: BatchTagNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes: list[Note] = []
    for note_id in dict.fromkeys(payload.note_ids):
        notes.append(_get_owned_note(db, current_user, note_id))

    tag_ids = list(dict.fromkeys(payload.tag_ids))
    for tag_id in tag_ids:
        tag = db.get(Tag, tag_id)
        if tag is None or tag.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    for note in notes:
        if payload.mode == "replace":
            db.execute(delete(note_tags).where(note_tags.c.note_id == note.id))
            for tag_id in tag_ids:
                db.execute(note_tags.insert().values(note_id=note.id, tag_id=tag_id))
            continue

        if payload.mode == "add":
            existing_tag_ids = set(
                db.scalars(select(note_tags.c.tag_id).where(note_tags.c.note_id == note.id)).all()
            )
            for tag_id in tag_ids:
                if tag_id not in existing_tag_ids:
                    db.execute(note_tags.insert().values(note_id=note.id, tag_id=tag_id))
            continue

        if tag_ids:
            db.execute(
                delete(note_tags).where(
                    note_tags.c.note_id == note.id,
                    note_tags.c.tag_id.in_(tag_ids),
                )
            )

    db.commit()
    return {
        "updated_count": len(notes),
        "items": [_serialize_note_with_tags(db, note) for note in notes],
    }


@router.post("/export")
def export_notes(
    payload: ExportNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = _get_unique_owned_notes(db, current_user, payload.note_ids)
    export_dir = Path(get_settings().storage_dir) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    exported_at = shanghai_now()
    file_name = f"xhs-notes-u{current_user.id}-{exported_at.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}.{payload.format}"
    file_path = export_dir / file_name
    if payload.format == "csv":
        file_path.write_text("\ufeff" + _build_notes_csv(db, notes), encoding="utf-8")
    else:
        export_payload = {
            "platform": "xhs",
            "format": payload.format,
            "exported_at": exported_at.isoformat(),
            "total": len(notes),
            "items": [_serialize_note_with_tags(db, note) for note in notes],
        }
        file_path.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "exported_count": len(notes),
        "file_name": file_name,
        "file_path": str(file_path.resolve()),
        "download_url": f"/api/files/exports/{file_name}",
    }

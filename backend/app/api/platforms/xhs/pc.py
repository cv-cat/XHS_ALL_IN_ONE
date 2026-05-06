from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.xhs.pc_api_adapter import XhsPcApiAdapter
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import decrypt_text
from backend.app.models import AccountCookieVersion, PlatformAccount, User
from backend.app.services.mock_data import sample_notes

router = APIRouter(prefix="/xhs/pc", tags=["xhs-pc"])


class SearchNotesRequest(BaseModel):
    account_id: int
    keyword: str = Field(min_length=1, max_length=120)
    page: int = Field(default=1, ge=1)
    sort_type_choice: int = Field(default=0, ge=0, le=4)
    note_type: int = Field(default=0, ge=0, le=2)
    note_time: int = Field(default=0, ge=0, le=3)
    note_range: int = Field(default=0, ge=0, le=3)
    pos_distance: int = Field(default=0, ge=0, le=2)
    geo: str = ""


class NoteDetailRequest(BaseModel):
    account_id: int
    url: str = Field(min_length=1)


class NoteCommentsRequest(BaseModel):
    account_id: int
    note_url: str = Field(min_length=1)


def get_xhs_pc_api_adapter_factory():
    return XhsPcApiAdapter


def _cookies_to_string(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    if stripped.startswith("{"):
        cookies = json.loads(stripped)
        return "; ".join(f"{key}={cookie_value}" for key, cookie_value in cookies.items())
    return stripped


def _metric(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    elif text.lower().endswith("w"):
        multiplier = 10000
        text = text[:-1]
    number_match = re.search(r"\d+(?:\.\d+)?", text)
    if not number_match:
        return 0
    return int(float(number_match.group(0)) * multiplier)


def _first_url(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return _first_url(value[0])
    if isinstance(value, dict):
        info_list = value.get("info_list")
        if isinstance(info_list, list) and len(info_list) > 1 and isinstance(info_list[1], dict):
            preferred_url = info_list[1].get("url")
            if preferred_url:
                return str(preferred_url)
        for key in ("url_default", "url_pre", "url", "src"):
            if value.get(key):
                return str(value[key])
        for nested in ("info_list", "image_list", "images"):
            if value.get(nested):
                return _first_url(value[nested])
    return ""


def _all_urls(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        urls: list[str] = []
        for item in value:
            urls.extend(_all_urls(item))
        return [url for index, url in enumerate(urls) if url and url not in urls[:index]]
    if isinstance(value, dict):
        direct = _first_url(value)
        if direct:
            return [direct]
        urls: list[str] = []
        for nested in ("info_list", "image_list", "images"):
            if value.get(nested):
                urls.extend(_all_urls(value[nested]))
        return [url for index, url in enumerate(urls) if url and url not in urls[:index]]
    return []


def _tag_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        if isinstance(item, str):
            tag = item
        elif isinstance(item, dict):
            tag = item.get("name") or item.get("tag_name") or item.get("title") or ""
        else:
            tag = ""
        if tag and tag not in tags:
            tags.append(str(tag))
    return tags


def _note_url(note_id: str, item: dict[str, Any], card: dict[str, Any]) -> str:
    xsec_token = card.get("xsec_token") or item.get("xsec_token") or ""
    if note_id and xsec_token:
        xsec_source = card.get("xsec_source") or item.get("xsec_source") or "pc_feed"
        return f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"
    for value in (
        card.get("note_url"),
        card.get("url"),
        card.get("share_url"),
        item.get("note_url"),
        item.get("url"),
        item.get("share_url"),
    ):
        if isinstance(value, str) and value:
            return value
    if not note_id:
        return ""
    return f"https://www.xiaohongshu.com/explore/{note_id}"


def _comment_id(comment: dict[str, Any]) -> str:
    return str(comment.get("comment_id") or comment.get("id") or comment.get("commentId") or "")


def _comment_user(comment: dict[str, Any]) -> dict[str, Any]:
    return comment.get("user_info") or comment.get("user") or comment.get("author") or {}


def _comment_children(comment: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("sub_comments", "sub_comment", "comments", "replies", "children"):
        value = comment.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    sub_comment_payload = comment.get("sub_comment_info")
    if isinstance(sub_comment_payload, dict):
        value = sub_comment_payload.get("comments")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_comment(comment: dict[str, Any], parent_comment_id: str | None = None) -> dict[str, Any]:
    user = _comment_user(comment)
    return {
        "comment_id": _comment_id(comment),
        "user_name": str(user.get("nickname") or user.get("name") or comment.get("user_name") or ""),
        "user_id": str(user.get("user_id") or user.get("id") or comment.get("user_id") or "") or None,
        "content": str(comment.get("content") or comment.get("text") or comment.get("desc") or ""),
        "like_count": _metric(comment.get("like_count") or comment.get("liked_count") or comment.get("likes")),
        "parent_comment_id": parent_comment_id,
        "created_at_remote": comment.get("create_time") or comment.get("created_at") or comment.get("time"),
        "raw_json": comment,
    }


def _flatten_comments(comments: list[dict[str, Any]], parent_comment_id: str | None = None) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for comment in comments:
        normalized = _normalize_comment(comment, parent_comment_id=parent_comment_id)
        if normalized["comment_id"]:
            flattened.append(normalized)
            child_parent_id = normalized["comment_id"]
        else:
            child_parent_id = parent_comment_id
        flattened.extend(_flatten_comments(_comment_children(comment), parent_comment_id=child_parent_id))
    return flattened


def _extract_comment_list(raw_payload: Any) -> list[dict[str, Any]]:
    if isinstance(raw_payload, list):
        return [item for item in raw_payload if isinstance(item, dict)]
    if not isinstance(raw_payload, dict):
        return []
    data = raw_payload.get("data") if isinstance(raw_payload.get("data"), dict) else raw_payload
    for key in ("comments", "items", "list"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def normalize_comment_payload(raw_payload: Any) -> list[dict[str, Any]]:
    return _flatten_comments(_extract_comment_list(raw_payload))


def _normalize_search_item(item: dict[str, Any]) -> dict[str, Any]:
    card = item.get("note_card") or item.get("note") or item
    author = card.get("user") or card.get("author") or {}
    interact = card.get("interact_info") or card.get("interaction") or {}
    note_id = card.get("note_id") or card.get("id") or item.get("id") or ""
    timestamp = card.get("time") or card.get("create_time") or item.get("time") or item.get("create_time") or 0
    return {
        "note_id": note_id,
        "note_url": _note_url(str(note_id), item, card),
        "title": card.get("display_title") or card.get("title") or "",
        "content": card.get("desc") or card.get("content") or "",
        "author_id": author.get("user_id") or author.get("id") or "",
        "author_name": author.get("nickname") or author.get("name") or "",
        "author_avatar": author.get("avatar") or author.get("avatar_url") or "",
        "cover_url": _first_url(card.get("cover") or card.get("image_list") or card.get("images")),
        "image_urls": _all_urls(card.get("image_list") or card.get("images") or card.get("cover")),
        "likes": _metric(interact.get("liked_count") or interact.get("likes")),
        "collects": _metric(interact.get("collected_count") or interact.get("collects")),
        "comments": _metric(interact.get("comment_count") or interact.get("comments")),
        "shares": _metric(interact.get("share_count") or interact.get("shares")),
        "type": card.get("type") or item.get("model_type") or "",
        "timestamp": timestamp,
        "raw": item,
    }


def _video_url(card: dict[str, Any]) -> str:
    for key in ("video_addr", "video_url"):
        if card.get(key):
            return str(card[key])
    video_info = card.get("video") if isinstance(card.get("video"), dict) else {}
    stream_info = video_info.get("media", {}).get("stream", {}) if isinstance(video_info, dict) else {}
    for codec in ("h264", "h265", "av1"):
        streams = stream_info.get(codec, []) if isinstance(stream_info, dict) else []
        if isinstance(streams, list) and streams:
            first_stream = streams[0] if isinstance(streams[0], dict) else {}
            if first_stream.get("master_url") or first_stream.get("url"):
                return str(first_stream.get("master_url") or first_stream.get("url"))
    consumer = video_info.get("consumer") if isinstance(video_info.get("consumer"), dict) else {}
    origin_key = consumer.get("origin_video_key")
    return f"https://sns-video-bd.xhscdn.com/{origin_key}" if origin_key else ""


def _normalize_detail_payload(raw_payload: dict[str, Any], source_url: str = "") -> dict[str, Any]:
    data = (raw_payload or {}).get("data") or {}
    items = data.get("items") or []
    item = items[0] if items and isinstance(items[0], dict) else (data if isinstance(data, dict) else {})
    normalized = _normalize_search_item(item)
    card = item.get("note_card") or item.get("note") or item
    images = _all_urls(card.get("image_list") or card.get("images") or card.get("cover"))
    if source_url:
        normalized["note_url"] = source_url
    normalized["image_urls"] = images
    video_url = _video_url(card)
    normalized["video_url"] = video_url
    normalized["video_addr"] = video_url
    normalized["tags"] = _tag_names(card.get("tag_list") or card.get("tags") or card.get("topics"))
    normalized["raw"] = raw_payload
    return normalized


def _get_owned_pc_account_cookies(db: Session, current_user: User, account_id: int) -> str:
    account = db.get(PlatformAccount, account_id)
    if (
        account is None
        or account.user_id != current_user.id
        or account.platform != "xhs"
        or account.sub_type != "pc"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    cookie_version = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account.id)
        .order_by(AccountCookieVersion.created_at.desc())
    ).first()
    if cookie_version is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account has no cookies")
    return _cookies_to_string(decrypt_text(cookie_version.encrypted_cookies))


@router.post("/search/notes")
def search_notes(
    payload: SearchNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    cookies = _get_owned_pc_account_cookies(db, current_user, payload.account_id)
    success, message, raw_payload = adapter_factory(cookies).search_note(
        payload.keyword,
        page=payload.page,
        sort_type_choice=payload.sort_type_choice,
        note_type=payload.note_type,
        note_time=payload.note_time,
        note_range=payload.note_range,
        pos_distance=payload.pos_distance,
        geo=payload.geo,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=message or "XHS note search failed",
        )

    data = (raw_payload or {}).get("data") or {}
    items = data.get("items") or []
    normalized_items = [
        _normalize_search_item(item)
        for item in items
        if isinstance(item, dict) and item.get("model_type") not in ("rec_query", "hot_query")
    ]
    return {
        "total": len(normalized_items),
        "page": payload.page,
        "page_size": data.get("page_size") or 20,
        "has_more": bool(data.get("has_more", False)),
        "items": normalized_items,
        "raw": raw_payload,
    }


@router.post("/search/users")
def search_users():
    return {"total": 1, "items": [{"id": "demo-user", "nickname": "运营研究员"}]}


@router.post("/notes/detail")
def note_detail(
    payload: NoteDetailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    cookies = _get_owned_pc_account_cookies(db, current_user, payload.account_id)
    success, message, raw_payload = adapter_factory(cookies).get_note_info(payload.url)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=message or "XHS note detail failed",
        )
    return _normalize_detail_payload(raw_payload or {}, source_url=payload.url)


@router.post("/notes/comments")
def note_comments(
    payload: NoteCommentsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    cookies = _get_owned_pc_account_cookies(db, current_user, payload.account_id)
    success, message, raw_payload = adapter_factory(cookies).get_note_comments(payload.note_url)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=message or "XHS note comments failed",
        )
    items = normalize_comment_payload(raw_payload)
    return {"total": len(items), "items": items}


def note_comments_placeholder():
    return {"total": 1, "items": [{"id": "comment-1", "content": "这个选题很有用"}]}


@router.post("/users/notes")
def user_notes():
    return {"total": len(sample_notes()), "items": sample_notes()}


@router.get("/homefeed/channels")
def homefeed_channels():
    return {"items": [{"id": "homefeed_recommend", "name": "推荐"}]}


@router.post("/homefeed/recommend")
def homefeed_recommend():
    return {"items": sample_notes()}

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.time import shanghai_now
from backend.app.models import AiDraft, KeywordGroup, MonitoringTarget, Note, NoteComment, PlatformAccount, PublishJob, Tag, User, note_tags

router = APIRouter(prefix="/xhs/analytics", tags=["xhs-analytics"])


class AnalyticsReportRequest(BaseModel):
    note_ids: list[int] = Field(default_factory=list)
    format: Literal["json"] = "json"


METRIC_KEYS = {
    "likes": ("likes", "liked_count", "like_count"),
    "collects": ("collects", "collected_count", "collect_count"),
    "comments": ("comments", "comment_count"),
    "shares": ("shares", "share_count"),
}


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().lower().replace(",", "")
        multiplier = 1
        if cleaned.endswith("w"):
            multiplier = 10000
            cleaned = cleaned[:-1]
        try:
            return int(float(cleaned) * multiplier)
        except ValueError:
            return 0
    return 0


def _raw_value(raw: dict[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in raw:
            return _as_int(raw.get(key))
        data = raw.get("data")
        if isinstance(data, dict) and key in data:
            return _as_int(data.get(key))
        note = raw.get("note")
        if isinstance(note, dict) and key in note:
            return _as_int(note.get(key))
    return 0


def _note_metrics(note: Note) -> dict[str, int]:
    raw = note.raw_json or {}
    metrics = {name: _raw_value(raw, keys) for name, keys in METRIC_KEYS.items()}
    metrics["engagement"] = sum(metrics.values())
    return metrics


def _owned_notes_statement(current_user: User):
    return (
        select(Note)
        .where(Note.user_id == current_user.id, Note.platform == "xhs")
    )


def _owned_notes(db: Session, current_user: User) -> list[Note]:
    return db.scalars(_owned_notes_statement(current_user).order_by(Note.created_at.desc())).all()


def _note_haystack(note: Note) -> str:
    return "\n".join(
        [
            note.note_id or "",
            note.title or "",
            note.content or "",
            note.author_name or "",
            str(note.raw_json or {}),
        ]
    ).lower()


def _note_matches_value(note: Note, value: str) -> bool:
    needle = value.strip().lower()
    if not needle:
        return False
    return needle in _note_haystack(note)


def _serialize_top_note(note: Note) -> dict[str, Any]:
    metrics = _note_metrics(note)
    return {
        "id": note.id,
        "note_id": note.note_id,
        "title": note.title,
        "author_name": note.author_name,
        "created_at": note.created_at.isoformat(),
        **metrics,
    }


def _serialize_draft(draft: AiDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "platform": draft.platform,
        "title": draft.title,
        "body": draft.body,
        "source_note_id": draft.source_note_id,
        "created_at": draft.created_at.isoformat(),
    }


def _get_owned_benchmark_target(db: Session, current_user: User, target_id: int) -> MonitoringTarget:
    target = db.get(MonitoringTarget, target_id)
    if target is None or target.user_id != current_user.id or target.platform != "xhs":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark target not found")
    if target.target_type not in {"account", "brand"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Benchmark target must be account or brand")
    return target


def _benchmark_matches(notes: list[Note], target: MonitoringTarget) -> list[Note]:
    matched = [note for note in notes if _note_matches_value(note, target.value)]
    return sorted(matched, key=lambda note: _note_metrics(note)["engagement"], reverse=True)


def _raw_topics(raw: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    for key in ("tags", "topics", "keywords"):
        value = raw.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    topics.append(item.strip().lstrip("#"))
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("tag") or item.get("keyword")
                    if isinstance(name, str) and name.strip():
                        topics.append(name.strip().lstrip("#"))
    return topics


def _topic_items(db: Session, current_user: User, notes: list[Note]) -> list[dict[str, Any]]:
    note_by_id = {note.id: note for note in notes}
    topic_note_ids: dict[str, set[int]] = defaultdict(set)

    tag_rows = db.execute(
        select(note_tags.c.note_id, Tag.name)
        .join(Tag, Tag.id == note_tags.c.tag_id)
        .where(Tag.user_id == current_user.id, note_tags.c.note_id.in_(note_by_id.keys() or [-1]))
    ).all()
    for note_id, tag_name in tag_rows:
        if tag_name:
            topic_note_ids[tag_name].add(note_id)

    for note in notes:
        for topic in _raw_topics(note.raw_json or {}):
            topic_note_ids[topic].add(note.id)

    items: list[dict[str, Any]] = []
    for keyword, note_ids in topic_note_ids.items():
        engagement = sum(_note_metrics(note_by_id[note_id])["engagement"] for note_id in note_ids if note_id in note_by_id)
        items.append({"keyword": keyword, "notes": len(note_ids), "engagement": engagement})
    return sorted(items, key=lambda item: (item["notes"], item["engagement"], item["keyword"]), reverse=True)


def _owned_comments(db: Session, current_user: User) -> list[NoteComment]:
    return db.scalars(
        select(NoteComment)
        .join(Note, NoteComment.note_id == Note.id)
        .where(Note.user_id == current_user.id, Note.platform == "xhs")
        .order_by(NoteComment.like_count.desc(), NoteComment.id.asc())
    ).all()


def _comments_for_notes(db: Session, current_user: User, note_ids: set[int]) -> list[NoteComment]:
    if not note_ids:
        return []
    return db.scalars(
        select(NoteComment)
        .join(Note, NoteComment.note_id == Note.id)
        .where(Note.user_id == current_user.id, Note.platform == "xhs", NoteComment.note_id.in_(note_ids))
        .order_by(NoteComment.like_count.desc(), NoteComment.id.asc())
    ).all()


def _comment_insight_payload(comments: list[NoteComment]) -> dict[str, Any]:
    repeated_terms = Counter()
    for comment in comments:
        for term in ("price", "link", "suitable", "how", "where", "recommend", "commute"):
            if term in comment.content.lower():
                repeated_terms[term] += 1
    return {
        "total_comments": len(comments),
        "question_count": len([comment for comment in comments if "?" in comment.content or "？" in comment.content]),
        "top_terms": [{"term": term, "count": count} for term, count in repeated_terms.most_common(10)],
        "top_comments": [
            {
                "id": comment.id,
                "note_id": comment.note_id,
                "user_name": comment.user_name,
                "content": comment.content,
                "like_count": comment.like_count,
            }
            for comment in comments[:10]
        ],
    }


def _owned_report_notes(db: Session, current_user: User, note_ids: list[int]) -> list[Note]:
    if not note_ids:
        return _owned_notes(db, current_user)

    unique_ids = list(dict.fromkeys(note_ids))
    notes = db.scalars(_owned_notes_statement(current_user).where(Note.id.in_(unique_ids))).all()
    notes_by_id = {note.id: note for note in notes}
    if set(notes_by_id) != set(unique_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report note not found")
    return [notes_by_id[note_id] for note_id in unique_ids]


def _benchmark_report_items(db: Session, current_user: User, notes: list[Note]) -> list[dict[str, Any]]:
    targets = db.scalars(
        select(MonitoringTarget)
        .where(
            MonitoringTarget.user_id == current_user.id,
            MonitoringTarget.platform == "xhs",
            MonitoringTarget.target_type.in_(("account", "brand")),
        )
        .order_by(MonitoringTarget.created_at.desc(), MonitoringTarget.id.desc())
    ).all()

    items: list[dict[str, Any]] = []
    for target in targets:
        matched = _benchmark_matches(notes, target)
        total_engagement = sum(_note_metrics(note)["engagement"] for note in matched)
        items.append(
            {
                "target_id": target.id,
                "target_type": target.target_type,
                "name": target.name or target.value,
                "value": target.value,
                "matched_notes": len(matched),
                "total_engagement": total_engagement,
                "average_engagement": round(total_engagement / len(matched), 2) if matched else 0,
                "top_notes": [_serialize_top_note(note) for note in matched[:5]],
            }
        )
    return sorted(items, key=lambda item: (item["total_engagement"], item["matched_notes"], item["name"]), reverse=True)


def _keyword_trend_items(db: Session, current_user: User, notes: list[Note]) -> list[dict[str, Any]]:
    groups = db.scalars(
        select(KeywordGroup)
        .where(KeywordGroup.user_id == current_user.id, KeywordGroup.platform == "xhs")
        .order_by(KeywordGroup.created_at.asc(), KeywordGroup.id.asc())
    ).all()

    items: list[dict[str, Any]] = []
    if groups:
        for group in groups:
            for keyword in group.keywords or []:
                keyword_text = str(keyword).strip()
                if not keyword_text:
                    continue
                matched = [note for note in notes if _note_matches_value(note, keyword_text)]
                engagement = sum(_note_metrics(note)["engagement"] for note in matched)
                items.append(
                    {
                        "keyword": keyword_text,
                        "group_id": group.id,
                        "group_name": group.name,
                        "notes": len(matched),
                        "engagement": engagement,
                        "top_notes": [_serialize_top_note(note) for note in sorted(matched, key=lambda note: _note_metrics(note)["engagement"], reverse=True)[:5]],
                    }
                )
        return items

    return [
        {
            "keyword": item["keyword"],
            "group_id": None,
            "group_name": "",
            "notes": item["notes"],
            "engagement": item["engagement"],
            "top_notes": [],
        }
        for item in _topic_items(db, current_user, notes)
    ]


def _build_report_payload(db: Session, current_user: User, notes: list[Note], generated_at: datetime) -> dict[str, Any]:
    comments = _comments_for_notes(db, current_user, {note.id for note in notes})
    top_notes = sorted(notes, key=lambda note: _note_metrics(note)["engagement"], reverse=True)
    topics = _topic_items(db, current_user, notes)
    total_engagement = sum(_note_metrics(note)["engagement"] for note in notes)
    benchmark_items = _benchmark_report_items(db, current_user, notes)
    summary = {
        "note_count": len(notes),
        "total_engagement": total_engagement,
        "comment_count": len(comments),
        "top_topics": topics[:10],
        "top_notes": [_serialize_top_note(note) for note in top_notes[:10]],
        "benchmark_count": len(benchmark_items),
    }
    return {
        "metadata": {
            "report_type": "operations",
            "platform": "xhs",
            "user_id": current_user.id,
            "generated_at": generated_at.isoformat(),
        },
        "summary": summary,
        "top_notes": [_serialize_top_note(note) for note in top_notes[:20]],
        "hot_topics": topics,
        "comment_insights": _comment_insight_payload(comments),
        "benchmarks": benchmark_items,
    }


def _write_report_file(current_user: User, payload: dict[str, Any]) -> tuple[str, Path]:
    export_dir = Path(get_settings().storage_dir) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"xhs-report-u{current_user.id}-{uuid4().hex}.json"
    file_path = export_dir / file_name
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_name, file_path


@router.get("/overview")
def overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = _owned_notes(db, current_user)
    comments = _owned_comments(db, current_user)
    accounts = db.scalars(
        select(PlatformAccount).where(PlatformAccount.user_id == current_user.id, PlatformAccount.platform == "xhs")
    ).all()
    pending_publishes = db.scalars(
        select(PublishJob)
        .join(PlatformAccount, PublishJob.platform_account_id == PlatformAccount.id)
        .where(
            PlatformAccount.user_id == current_user.id,
            PublishJob.platform == "xhs",
            PublishJob.status.in_(["pending", "uploading", "publishing", "scheduled"]),
        )
    ).all()
    today = shanghai_now().date()
    total_engagement = sum(_note_metrics(note)["engagement"] for note in notes)
    hot_topics = _topic_items(db, current_user, notes)[:5]
    recent_activity = [
        {"type": "note", "title": note.title or note.note_id, "status": "saved"} for note in notes[:5]
    ]
    return {
        "platform": "xhs",
        "today_crawls": len([note for note in notes if note.created_at.date() == today]),
        "saved_notes": len(notes),
        "pending_publishes": len(pending_publishes),
        "healthy_accounts": len([account for account in accounts if account.status in ("active", "healthy")]),
        "at_risk_accounts": len([account for account in accounts if account.status not in ("active", "healthy")]),
        "comment_count": len(comments),
        "total_engagement": total_engagement,
        "hot_topics": hot_topics,
        "recent_activity": recent_activity,
    }


@router.get("/top-content")
def top_content(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = sorted(_owned_notes(db, current_user), key=lambda note: _note_metrics(note)["engagement"], reverse=True)
    return {"items": [_serialize_top_note(note) for note in notes[:limit]]}


@router.get("/hot-topics")
def hot_topics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"items": _topic_items(db, current_user, _owned_notes(db, current_user))}


@router.get("/engagement")
def engagement(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    daily: dict[str, Counter] = defaultdict(Counter)
    for note in _owned_notes(db, current_user):
        metrics = _note_metrics(note)
        key = note.created_at.date().isoformat()
        daily[key].update(metrics)
    return {
        "items": [
            {
                "date": date,
                "likes": counter["likes"],
                "collects": counter["collects"],
                "comments": counter["comments"],
                "shares": counter["shares"],
                "engagement": counter["engagement"],
            }
            for date, counter in sorted(daily.items())
        ]
    }


@router.get("/keyword-trends")
def keyword_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"items": _keyword_trend_items(db, current_user, _owned_notes(db, current_user))}


@router.get("/comment-insights")
def comment_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comments = _owned_comments(db, current_user)
    repeated_terms = Counter()
    for comment in comments:
        for term in ("价格", "多少钱", "链接", "适合", "怎么", "哪里", "推荐", "通勤"):
            if term in comment.content:
                repeated_terms[term] += 1
    return {
        "total_comments": len(comments),
        "question_count": len([comment for comment in comments if "?" in comment.content or "？" in comment.content]),
        "top_terms": [{"term": term, "count": count} for term, count in repeated_terms.most_common(10)],
        "top_comments": [
            {
                "id": comment.id,
                "note_id": comment.note_id,
                "user_name": comment.user_name,
                "content": comment.content,
                "like_count": comment.like_count,
            }
            for comment in comments[:10]
        ],
    }


@router.post("/reports")
def create_report(
    payload: AnalyticsReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = _owned_report_notes(db, current_user, payload.note_ids)
    generated_at = shanghai_now()
    report_payload = _build_report_payload(db, current_user, notes, generated_at)
    file_name, file_path = _write_report_file(current_user, report_payload)
    return {
        "report_type": "operations",
        "generated_at": generated_at.isoformat(),
        "note_count": len(notes),
        "file_name": file_name,
        "file_path": str(file_path),
        "download_url": f"/api/files/exports/{file_name}",
        "summary": report_payload["summary"],
    }


@router.get("/benchmarks")
def benchmarks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notes = _owned_notes(db, current_user)
    targets = db.scalars(
        select(MonitoringTarget)
        .where(
            MonitoringTarget.user_id == current_user.id,
            MonitoringTarget.platform == "xhs",
            MonitoringTarget.target_type.in_(("account", "brand")),
        )
        .order_by(MonitoringTarget.created_at.desc(), MonitoringTarget.id.desc())
    ).all()

    items: list[dict[str, Any]] = []
    for target in targets:
        matched = _benchmark_matches(notes, target)
        total_engagement = sum(_note_metrics(note)["engagement"] for note in matched)
        items.append(
            {
                "target_id": target.id,
                "target_type": target.target_type,
                "name": target.name or target.value,
                "value": target.value,
                "status": target.status,
                "last_refreshed_at": target.last_refreshed_at.isoformat() if target.last_refreshed_at else None,
                "matched_notes": len(matched),
                "total_engagement": total_engagement,
                "average_engagement": round(total_engagement / len(matched), 2) if matched else 0,
                "top_notes": [_serialize_top_note(note) for note in matched[:5]],
            }
        )

    items = sorted(items, key=lambda item: (item["total_engagement"], item["matched_notes"], item["name"]), reverse=True)
    total_matched = sum(item["matched_notes"] for item in items)
    total_engagement = sum(item["total_engagement"] for item in items)
    return {
        "total_targets": len(items),
        "matched_notes": total_matched,
        "total_engagement": total_engagement,
        "average_engagement": round(total_engagement / total_matched, 2) if total_matched else 0,
        "items": items,
    }


@router.post("/benchmarks/{target_id}/create-drafts")
def create_benchmark_drafts(
    target_id: int,
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_benchmark_target(db, current_user, target_id)
    matched = _benchmark_matches(_owned_notes(db, current_user), target)[:limit]
    drafts = [
        AiDraft(
            user_id=current_user.id,
            platform="xhs",
            title=note.title,
            body=note.content,
            source_note_id=note.id,
        )
        for note in matched
    ]
    db.add_all(drafts)
    db.commit()
    for draft in drafts:
        db.refresh(draft)
    return {
        "created_count": len(drafts),
        "items": [_serialize_draft(draft) for draft in drafts],
    }

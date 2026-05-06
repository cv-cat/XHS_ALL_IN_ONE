from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.security import encrypt_text
from backend.app.core.time import shanghai_now
from backend.app.models import AccountCookieVersion, PlatformAccount
from xhs_utils.cookie_util import trans_cookies


def account_profile_from_user_info(user_info: dict[str, Any]) -> dict[str, Any]:
    profile = user_info.get("profile")
    if isinstance(profile, dict):
        return profile
    return {}


def decode_cookie_text(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if not stripped:
        return {}
    if stripped.startswith("{"):
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    return trans_cookies(stripped)


def cookie_header_from_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if not stripped.startswith("{"):
        return stripped
    cookies = decode_cookie_text(stripped)
    return "; ".join(f"{key}={cookie_value}" for key, cookie_value in cookies.items())


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def enrich_user_info_with_xhs_self_profile(user_info: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data") if isinstance(response, dict) else {}
    if not isinstance(data, dict):
        return user_info
    basic_info = data.get("basic_info")
    if not isinstance(basic_info, dict):
        basic_info = {}

    interaction_counts: dict[str, Any] = {}
    interactions = data.get("interactions")
    if isinstance(interactions, list):
        for item in interactions:
            if not isinstance(item, dict):
                continue
            interaction_type = item.get("type")
            if interaction_type:
                interaction_counts[str(interaction_type)] = _first_present(item.get("i18n_count"), item.get("count"))

    profile = {
        **account_profile_from_user_info(user_info),
        "red_id": _first_present(basic_info.get("red_id"), account_profile_from_user_info(user_info).get("red_id"), ""),
        "description": _first_present(basic_info.get("desc"), account_profile_from_user_info(user_info).get("description"), ""),
        "ip_location": _first_present(basic_info.get("ip_location"), account_profile_from_user_info(user_info).get("ip_location"), ""),
        "gender": _first_present(basic_info.get("gender"), account_profile_from_user_info(user_info).get("gender")),
        "followers": _first_present(interaction_counts.get("fans"), account_profile_from_user_info(user_info).get("followers")),
        "following": _first_present(interaction_counts.get("follows"), account_profile_from_user_info(user_info).get("following")),
        "likes": _first_present(interaction_counts.get("interaction"), account_profile_from_user_info(user_info).get("likes")),
        "raw": response,
    }
    return {
        **user_info,
        "nickname": _first_present(basic_info.get("nickname"), user_info.get("nickname"), ""),
        "avatar_url": _first_present(basic_info.get("images"), basic_info.get("imageb"), user_info.get("avatar_url"), ""),
        "profile": profile,
    }


def serialize_account(account: PlatformAccount, action: str | None = None) -> dict[str, Any]:
    try:
        profile = json.loads(account.profile_json or "{}")
        if not isinstance(profile, dict):
            profile = {}
    except json.JSONDecodeError:
        profile = {}

    payload = {
        "id": account.id,
        "platform": account.platform,
        "sub_type": account.sub_type,
        "external_user_id": account.external_user_id,
        "nickname": account.nickname,
        "avatar_url": account.avatar_url,
        "status": account.status,
        "status_message": account.status_message,
        "profile": profile,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": (account.updated_at or account.created_at).isoformat() if (account.updated_at or account.created_at) else None,
    }
    if action:
        payload["action"] = action
    return payload


def upsert_platform_account_from_login(
    *,
    db: Session,
    user_id: int,
    platform: str,
    sub_type: str,
    user_info: dict[str, Any],
    cookies_text: str,
) -> tuple[PlatformAccount, str]:
    external_user_id = user_info.get("external_user_id", "") or ""
    account = None
    if external_user_id:
        account = db.scalar(
            select(PlatformAccount).where(
                PlatformAccount.user_id == user_id,
                PlatformAccount.platform == platform,
                PlatformAccount.sub_type == sub_type,
                PlatformAccount.external_user_id == external_user_id,
            )
        )

    action = "updated" if account is not None else "created"
    now = shanghai_now()
    if account is None:
        account = PlatformAccount(
            user_id=user_id,
            platform=platform,
            sub_type=sub_type,
            external_user_id=external_user_id,
            created_at=now,
        )
        db.add(account)

    account.nickname = user_info.get("nickname", "") or account.nickname or ""
    account.avatar_url = user_info.get("avatar_url", "") or account.avatar_url or ""
    account.external_user_id = external_user_id or account.external_user_id
    account.status = "active"
    account.status_message = ""
    account.profile_json = json.dumps(account_profile_from_user_info(user_info), ensure_ascii=False, separators=(",", ":"))
    account.updated_at = now
    db.flush()
    db.add(
        AccountCookieVersion(
            platform_account_id=account.id,
            encrypted_cookies=encrypt_text(cookies_text),
        )
    )
    return account, action

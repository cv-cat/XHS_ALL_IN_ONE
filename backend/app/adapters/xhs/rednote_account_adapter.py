from __future__ import annotations

from typing import Any

import requests

from backend.app.services.account_service import enrich_user_info_with_xhs_self_profile
from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_util import generate_headers


class RednoteAccountError(RuntimeError):
    """Base class for user-safe Rednote account validation failures."""


class RednoteVerificationRequiredError(RednoteAccountError):
    """The platform requires an interactive verification step."""


class RednoteSessionInvalidError(RednoteAccountError):
    """The supplied session is missing, expired, or unauthenticated."""


class RednoteRequestUnavailableError(RednoteAccountError):
    """The remote health check could not be completed."""


_VERIFICATION_MARKERS = (
    "captcha",
    "verify",
    "verification",
    "risk",
    "验证",
    "验证码",
    "风险",
)
_SESSION_INVALID_MARKERS = (
    "login required",
    "sign in required",
    "not logged in",
    "logged out",
    "unauthenticated",
    "unauthorized",
    "session expired",
    "session invalid",
    "invalid session",
    "cookie expired",
    "invalid cookie",
    "token expired",
    "未登录",
    "请登录",
    "登录失效",
    "登录过期",
    "会话过期",
    "会话失效",
    "无效会话",
)
_TEMPORARY_MARKERS = (
    "temporary",
    "temporarily",
    "unavailable",
    "service busy",
    "try again",
    "retry",
    "rate",
    "too many",
    "frequent",
    "throttle",
    "later",
    "timeout",
    "服务繁忙",
    "暂时",
    "稍后",
    "重试",
    "频繁",
    "限流",
    "请求过多",
    "超时",
)


def _rednote_failure_kind(status_code: int, payload: Any) -> str | None:
    """Classify only evidence-backed auth failures; unknown failures stay temporary."""
    message = str(
        (payload.get("msg") or payload.get("message"))
        if isinstance(payload, dict)
        else ""
    ).lower()
    if any(marker in message for marker in _VERIFICATION_MARKERS):
        return "verification"
    if any(marker in message for marker in _SESSION_INVALID_MARKERS):
        return "session_invalid"
    if any(marker in message for marker in _TEMPORARY_MARKERS):
        return "unavailable"
    if 300 <= status_code < 400 or status_code == 401:
        return "session_invalid"
    if status_code >= 400:
        return "unavailable"
    if not isinstance(payload, dict) or not payload.get("success"):
        return "unavailable"
    return None


class RednotePcAccountAdapter:
    """Validate a Rednote PC cookie without falling back to China-site APIs."""

    base_url = "https://webapi.rednote.com"
    frontend_origin = "https://www.rednote.com"
    required_cookie_names = ("a1", "web_session")

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.trust_env = False

    @classmethod
    def _headers(cls, cookies: dict[str, Any], api: str) -> dict[str, str]:
        missing = [name for name in cls.required_cookie_names if not cookies.get(name)]
        if missing:
            raise RednoteSessionInvalidError("Rednote session is missing required cookies")
        a1 = str(cookies["a1"])
        try:
            headers, _ = generate_headers(a1, api, method="GET")
        except Exception as exc:
            raise RednoteRequestUnavailableError(
                "Rednote account request signing is temporarily unavailable"
            ) from exc
        headers.update(
            {
                "authority": "webapi.rednote.com",
                "origin": cls.frontend_origin,
                "referer": f"{cls.frontend_origin}/",
                "accept-language": "en-GB,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "sec-ch-ua": (
                    '"Not_A Brand";v="99", "Chromium";v="145", '
                    '"Google Chrome";v="145"'
                ),
                "sec-fetch-site": "same-site",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "user-agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
                ),
            }
        )
        return headers

    def _get(self, api: str, cookies: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}{api}",
                headers=self._headers(cookies, api),
                cookies=cookies,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                raise RednoteSessionInvalidError(
                    "Rednote account check redirected to authentication"
                )
            try:
                payload = response.json()
            except ValueError:
                payload = None
            failure_kind = _rednote_failure_kind(response.status_code, payload)
            if failure_kind == "verification":
                raise RednoteVerificationRequiredError(
                    "Rednote session requires verification"
                )
            if failure_kind == "session_invalid":
                raise RednoteSessionInvalidError(
                    "Rednote session is invalid or expired"
                )
            if failure_kind == "unavailable":
                raise RednoteRequestUnavailableError(
                    "Rednote account check is temporarily unavailable"
                )
            response.raise_for_status()
        except RednoteAccountError:
            raise
        except requests.RequestException as exc:
            raise RednoteRequestUnavailableError("Rednote account check is temporarily unavailable") from exc
        if not isinstance(payload, dict):
            raise RednoteRequestUnavailableError(
                "Rednote account response was not valid JSON"
            )
        return payload

    def get_user_info(self, cookies: dict[str, Any]) -> dict[str, Any]:
        identity_response = self._get("/api/sns/web/v2/user/me", cookies)
        data = identity_response.get("data")
        if not isinstance(data, dict):
            raise RednoteSessionInvalidError("Rednote identity response had no data")

        external_user_id = str(data.get("user_id") or data.get("userId") or "")
        nickname = str(data.get("nickname") or data.get("nickName") or "")
        if not external_user_id or not nickname or bool(data.get("guest")):
            raise RednoteSessionInvalidError("Rednote session is not authenticated")

        user_info: dict[str, Any] = {
            "external_user_id": external_user_id,
            "nickname": nickname,
            "avatar_url": data.get("images") or data.get("imageb") or "",
            "profile": {
                "site": "rednote",
                "red_id": data.get("red_id") or data.get("redId") or "",
                "description": data.get("desc") or "",
                "gender": data.get("gender"),
            },
        }

        profile_response = self._get("/api/sns/web/v1/user/selfinfo", cookies)
        user_info = enrich_user_info_with_xhs_self_profile(user_info, profile_response)
        profile = user_info.setdefault("profile", {})
        profile["site"] = "rednote"
        # The account matrix needs normalized profile fields, not a complete
        # authenticated response snapshot. Avoid retaining extra account data.
        profile.pop("raw", None)
        profile.pop("ip_location", None)
        return user_info

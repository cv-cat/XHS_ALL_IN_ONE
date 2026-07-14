from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from backend.app.adapters.xhs.rednote_account_adapter import (
    RednoteAccountError,
    RednoteRequestUnavailableError,
    RednoteSessionInvalidError,
    RednoteVerificationRequiredError,
    _rednote_failure_kind,
)
from xhs_utils.http_util import REQUEST_TIMEOUT
from xhs_utils.xhs_util import (
    generate_headers,
    generate_x_rap_param,
    splice_str,
    trans_cookies,
)


class RednotePcApiAdapter:
    """Collect the Rednote profile-list and note-detail paths verified locally."""

    base_url = "https://webapi.rednote.com"
    frontend_origin = "https://www.rednote.com"
    required_cookie_names = ("a1", "web_session")

    def __init__(self, cookies: str) -> None:
        self.cookies = trans_cookies(cookies)
        self.session = requests.Session()
        self.session.trust_env = False

    @classmethod
    def _parse_url(cls, url: str, expected_prefix: str) -> tuple[Any, str] | None:
        if len(url) > 4096:
            return None
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError:
            return None
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
            or hostname not in {"rednote.com", "www.rednote.com"}
        ):
            return None
        expected_parts = [part for part in expected_prefix.split("/") if part]
        path_parts = [part for part in parsed.path.split("/") if part]
        if (
            len(path_parts) != len(expected_parts) + 1
            or path_parts[:-1] != expected_parts
        ):
            return None
        resource_id = path_parts[-1]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", resource_id):
            return None
        return parsed, resource_id

    def _headers(
        self,
        api: str,
        data: Any = "",
        method: str = "GET",
    ) -> tuple[dict[str, str], Any]:
        missing = [
            name for name in self.required_cookie_names if not self.cookies.get(name)
        ]
        if missing:
            raise RednoteSessionInvalidError(
                "Rednote session is missing required cookies"
            )
        try:
            headers, encoded_data = generate_headers(
                str(self.cookies["a1"]),
                api,
                data,
                method=method,
            )
        except Exception as exc:
            raise RednoteRequestUnavailableError(
                "Rednote request signing is temporarily unavailable"
            ) from exc
        headers.update(
            {
                "authority": "webapi.rednote.com",
                "origin": self.frontend_origin,
                "referer": f"{self.frontend_origin}/",
                "accept-language": "en-GB,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "sec-ch-ua": (
                    '"Not_A Brand";v="99", "Chromium";v="145", '
                    '"Google Chrome";v="145"'
                ),
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "sec-fetch-site": "same-site",
                "user-agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/145.0.0.0 Safari/537.36"
                ),
            }
        )
        return headers, encoded_data

    @staticmethod
    def _result(response: requests.Response) -> tuple[bool, str, dict[str, Any] | None]:
        try:
            if 300 <= response.status_code < 400:
                raise RednoteSessionInvalidError(
                    "Rednote collection redirected to authentication"
                )
            try:
                payload = response.json()
            except ValueError:
                payload = None
            failure_kind = _rednote_failure_kind(response.status_code, payload)
            if failure_kind == "verification":
                raise RednoteVerificationRequiredError(
                    "Rednote requires interactive verification"
                )
            if failure_kind == "session_invalid":
                raise RednoteSessionInvalidError(
                    "Rednote session is invalid or expired"
                )
            if failure_kind == "unavailable":
                raise RednoteRequestUnavailableError(
                    "Rednote collection is temporarily unavailable"
                )
            response.raise_for_status()
        except RednoteAccountError:
            raise
        except requests.RequestException as exc:
            raise RednoteRequestUnavailableError(
                "Rednote collection is temporarily unavailable"
            ) from exc
        if not isinstance(payload, dict):
            raise RednoteRequestUnavailableError(
                "Rednote collection is temporarily unavailable"
            )
        return True, str(payload.get("msg") or "ok"), payload

    @staticmethod
    def _note_id(item: dict[str, Any]) -> str:
        card = item.get("note_card") or item.get("note") or item
        if not isinstance(card, dict):
            return ""
        return str(card.get("note_id") or card.get("id") or "")

    def get_user_notes(self, user_url: str) -> tuple[bool, str, list[dict[str, Any]] | None]:
        parsed_resource = self._parse_url(user_url, "/user/profile/")
        if parsed_resource is None:
            return False, "A Rednote profile URL is required", None
        parsed, user_id = parsed_resource
        query = parse_qs(parsed.query, keep_blank_values=True)
        xsec_token = query.get("xsec_token", [""])[-1]
        xsec_source = query.get("xsec_source", ["pc_search"])[-1]
        cursor = ""
        notes: list[dict[str, Any]] = []

        for _ in range(1000):
            api = splice_str(
                "/api/sns/web/v1/user_posted",
                {
                    "num": "30",
                    "cursor": cursor,
                    "user_id": user_id,
                    "image_formats": "jpg,webp,avif",
                    "xsec_token": xsec_token,
                    "xsec_source": xsec_source,
                },
            )
            headers, _ = self._headers(api)
            try:
                response = self.session.get(
                    f"{self.base_url}{api}",
                    headers=headers,
                    cookies=self.cookies,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                raise RednoteRequestUnavailableError(
                    "Rednote collection is temporarily unavailable"
                ) from exc
            success, message, payload = self._result(response)
            if not success or payload is None:
                return False, message, None
            data = payload.get("data")
            if not isinstance(data, dict):
                raise RednoteRequestUnavailableError(
                    "Rednote profile response had no data"
                )
            page_notes = data.get("notes") or []
            if not isinstance(page_notes, list):
                raise RednoteRequestUnavailableError(
                    "Rednote profile response had invalid notes"
                )
            notes.extend(item for item in page_notes if isinstance(item, dict))
            if not data.get("has_more"):
                return True, message, notes
            next_cursor = str(data.get("cursor") or "")
            if not next_cursor or next_cursor == cursor:
                raise RednoteRequestUnavailableError(
                    "Rednote profile pagination did not advance"
                )
            cursor = next_cursor
        raise RednoteRequestUnavailableError(
            "Rednote profile pagination exceeded the safety limit"
        )

    def get_note_info(self, url: str) -> tuple[bool, str, dict[str, Any] | None]:
        parsed_resource = self._parse_url(url, "/explore/")
        if parsed_resource is None:
            return False, "A Rednote note URL is required", None
        parsed, note_id = parsed_resource
        query = parse_qs(parsed.query, keep_blank_values=True)
        api = "/api/sns/web/v1/feed"
        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": "1"},
            "xsec_source": query.get("xsec_source", ["pc_search"])[-1],
            "xsec_token": query.get("xsec_token", [""])[-1],
        }
        headers, encoded_data = self._headers(api, data, method="POST")
        try:
            headers["x-rap-param"] = generate_x_rap_param(api, encoded_data)
        except Exception as exc:
            raise RednoteRequestUnavailableError(
                "Rednote request signing is temporarily unavailable"
            ) from exc
        headers["xy-direction"] = "13"
        try:
            response = self.session.post(
                f"{self.base_url}{api}",
                headers=headers,
                data=encoded_data,
                cookies=self.cookies,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise RednoteRequestUnavailableError(
                "Rednote collection is temporarily unavailable"
            ) from exc
        success, message, payload = self._result(response)
        if not success or payload is None:
            return False, message, None
        data_payload = payload.get("data")
        items = data_payload.get("items") if isinstance(data_payload, dict) else None
        matching_item = next(
            (
                item
                for item in items or []
                if isinstance(item, dict) and self._note_id(item) == note_id
            ),
            None,
        )
        if matching_item is None:
            return False, "Rednote note response did not match the requested note", None
        normalized_payload = {
            **payload,
            "data": {**data_payload, "items": [matching_item]},
        }
        return True, message, normalized_payload

    def search_note(self, *args, **kwargs) -> Any:
        return False, "Rednote search collection is not supported", None

    def get_note_comments(self, *args, **kwargs) -> Any:
        return False, "Rednote comment collection is not supported", None

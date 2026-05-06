from __future__ import annotations

from typing import Any

from backend.app.adapters.xhs.request_env import direct_xhs_request_env


class XhsPcLoginAdapter:
    def create_qrcode(self) -> dict[str, Any]:
        with direct_xhs_request_env():
            from apis.xhs_pc_login_apis import XHSLoginApi

            api = XHSLoginApi()
            cookies = api.generate_init_cookies()
            success, message, payload = api.generate_qrcode(cookies)
        if not success or not payload:
            raise RuntimeError(message)
        return {
            "cookies": payload["cookies"],
            "qr_id": payload["qr_id"],
            "code": payload["code"],
            "qr_url": payload["qr_url"],
        }

    def check_qrcode_status(self, qr_id: str, code: str, cookies: dict[str, Any]) -> dict[str, Any]:
        with direct_xhs_request_env():
            from apis.xhs_pc_login_apis import XHSLoginApi

            api = XHSLoginApi()
            success, message, updated_cookies = api.check_qrcode_status(qr_id, code, cookies)
        status = "confirmed" if success else "pending"
        if "过期" in message or "expired" in message.lower():
            status = "expired"
        if "确认" in message or "confirm" in message.lower():
            status = "scanned"
        return {"status": status, "cookies": updated_cookies}

    def get_user_info(self, cookies: dict[str, Any]) -> dict[str, Any]:
        with direct_xhs_request_env():
            from apis.xhs_pc_login_apis import XHSLoginApi

            api = XHSLoginApi()
            success, data, _ = api.get_user_info(cookies)
        if not success:
            raise RuntimeError("Failed to fetch XHS user info")
        return {
            "external_user_id": data.get("user_id", ""),
            "nickname": data.get("nickname", ""),
            "avatar_url": data.get("images") or data.get("imageb") or "",
            "profile": {
                "red_id": data.get("red_id") or data.get("redId") or "",
                "followers": data.get("fans") or data.get("followers") or data.get("follower_count"),
                "following": data.get("follows") or data.get("following") or data.get("following_count"),
                "likes": data.get("liked_count") or data.get("likes") or data.get("like_count"),
                "raw": data,
            },
        }

    def create_phone_session(self, phone: str) -> dict[str, Any]:
        with direct_xhs_request_env():
            from apis.xhs_pc_login_apis import XHSLoginApi

            api = XHSLoginApi()
            cookies = api.generate_init_cookies()
            success, message, _ = api.send_phone_code(phone, cookies)
        if not success:
            raise RuntimeError(message)
        return {"cookies": cookies, "message": message or "sent"}

    def confirm_phone_login(self, phone: str, code: str, cookies: dict[str, Any]) -> dict[str, Any]:
        with direct_xhs_request_env():
            from apis.xhs_pc_login_apis import XHSLoginApi

            api = XHSLoginApi()
            success, message, payload = api.login_by_phone(phone, code, cookies)
        if not success or not payload:
            raise RuntimeError(message)
        return {"status": "confirmed", "cookies": payload["cookies"]}

from __future__ import annotations

from typing import Any

from backend.app.adapters.xhs.request_env import direct_xhs_request_env


class XhsPcApiAdapter:
    def __init__(self, cookies: str) -> None:
        self.cookies = cookies

    def search_note(
        self,
        keyword: str,
        page: int = 1,
        sort_type_choice: int = 0,
        note_type: int = 0,
        note_time: int = 0,
        note_range: int = 0,
        pos_distance: int = 0,
        geo: str = "",
    ) -> Any:
        with direct_xhs_request_env():
            from apis.xhs_pc_apis import XHS_Apis

            api = XHS_Apis()
            return api.search_note(
                query=keyword,
                page=page,
                cookies_str=self.cookies,
                sort_type_choice=sort_type_choice,
                note_type=note_type,
                note_time=note_time,
                note_range=note_range,
                pos_distance=pos_distance,
                geo=geo,
            )

    def get_note_info(self, url: str) -> Any:
        with direct_xhs_request_env():
            from apis.xhs_pc_apis import XHS_Apis

            api = XHS_Apis()
            return api.get_note_info(url=url, cookies_str=self.cookies)

    def get_note_comments(self, note_url: str) -> Any:
        with direct_xhs_request_env():
            from apis.xhs_pc_apis import XHS_Apis

            api = XHS_Apis()
            return api.get_note_all_comment(url=note_url, cookies_str=self.cookies)

    def get_user_notes(self, user_url: str) -> Any:
        with direct_xhs_request_env():
            from apis.xhs_pc_apis import XHS_Apis

            api = XHS_Apis()
            return api.get_user_all_notes(user_url=user_url, cookies_str=self.cookies)

    def get_self_info(self) -> Any:
        with direct_xhs_request_env():
            from apis.xhs_pc_apis import XHS_Apis

            api = XHS_Apis()
            success, message, payload = api.get_user_self_info(cookies_str=self.cookies)
        if not success or not payload:
            raise RuntimeError(message or "XHS self profile refresh failed")
        return payload

from __future__ import annotations

import json
from typing import Any, Protocol

import requests

from backend.app.models import ModelConfig


class TextAiClient(Protocol):
    def rewrite_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        instruction: str,
    ) -> str:
        ...

    def generate_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        topic: str,
        reference: str,
        instruction: str,
    ) -> dict[str, str]:
        ...

    def generate_titles(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        ...

    def generate_tags(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        ...

    def polish_text(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        text: str,
        instruction: str,
    ) -> str:
        ...


class ImageAiClient(Protocol):
    def generate_cover(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        size: str,
        style: str,
    ) -> dict[str, Any]:
        ...

    def generate_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        reference_images: list[str] | None = None,
    ) -> dict[str, Any]:
        ...

    def describe_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        image_url: str,
        instruction: str,
    ) -> str:
        ...


def _candidate_response_encodings(response: requests.Response) -> list[str]:
    encodings: list[str] = []
    for encoding in ("utf-8-sig", "utf-8", response.apparent_encoding, response.encoding):
        normalized = (encoding or "").strip()
        if normalized and normalized.lower() not in {item.lower() for item in encodings}:
            encodings.append(normalized)
    return encodings


def _load_json_response(response: requests.Response) -> Any:
    raw = response.content
    last_error: Exception | None = None
    for encoding in _candidate_response_encodings(response):
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc

    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        last_error = exc

    raise ValueError("AI response is not valid JSON") from last_error


class OpenAICompatibleTextClient:
    def _complete(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        if not model_config.base_url:
            raise ValueError("Text model base_url is required")
        if not model_config.model_name:
            raise ValueError("Text model_name is required")
        if not api_key:
            raise ValueError("Text model api_key is required")

        endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = _load_json_response(response)
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI response missing choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI response content is empty")
        return content.strip()

    def rewrite_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        instruction: str,
    ) -> str:
        return self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书内容运营编辑，负责在保留事实的前提下改写成自然、可发布的种草笔记。",
            user_prompt=(
                f"改写要求：{instruction or '提升表达、增强小红书语感'}\n\n"
                f"标题：{title}\n\n正文：\n{body}"
            ),
        )

    def generate_note(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        topic: str,
        reference: str,
        instruction: str,
    ) -> dict[str, str]:
        content = self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书内容策划，输出可发布的标题和正文。",
            user_prompt=(
                "请生成一篇小红书笔记，格式必须是：\n标题：...\n正文：...\n\n"
                f"选题：{topic}\n参考材料：{reference or '无'}\n要求：{instruction or '自然、有信息密度'}"
            ),
        )
        title = topic
        body = content
        for line in content.splitlines():
            if line.startswith("标题："):
                title = line.replace("标题：", "", 1).strip() or title
                break
        if "正文：" in content:
            body = content.split("正文：", 1)[1].strip()
        return {"title": title, "body": body}

    def generate_titles(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        content = self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书标题优化专家。",
            user_prompt=f"请给出 {count} 个小红书标题，每行一个。\n原标题：{title}\n正文：{body}",
        )
        return [line.strip(" -0123456789.、") for line in content.splitlines() if line.strip()][:count]

    def generate_tags(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        title: str,
        body: str,
        count: int,
    ) -> list[str]:
        content = self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书 SEO 和话题标签专家。",
            user_prompt=f"请给出 {count} 个小红书话题标签，只输出标签，用逗号或换行分隔。\n标题：{title}\n正文：{body}",
        )
        separators = content.replace("，", ",").replace("\n", ",").split(",")
        return [item.strip().lstrip("#") for item in separators if item.strip()][:count]

    def polish_text(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        text: str,
        instruction: str,
    ) -> str:
        return self._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书正文润色编辑。",
            user_prompt=f"润色要求：{instruction or '更自然、清晰、有种草感'}\n\n原文：\n{text}",
        )


class OpenAICompatibleImageClient:
    def _validate(self, *, model_config: ModelConfig, api_key: str) -> None:
        if not model_config.base_url:
            raise ValueError("Image model base_url is required")
        if not model_config.model_name:
            raise ValueError("Image model_name is required")
        if not api_key:
            raise ValueError("Image model api_key is required")

    def generate_cover(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        size: str,
        style: str,
    ) -> dict[str, Any]:
        return self.generate_image(
            model_config=model_config, api_key=api_key, prompt=f"{prompt}\nStyle: {style or 'clean XHS cover'}",
        )

    def generate_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        prompt: str,
        reference_images: list[str] | None = None,
    ) -> dict[str, Any]:
        self._validate(model_config=model_config, api_key=api_key)
        endpoint = f"{model_config.base_url.rstrip('/')}/images/generations"
        body: dict[str, Any] = {
            "model": model_config.model_name,
            "prompt": prompt,
            "response_format": "url",
        }
        if reference_images:
            resolved = [self._resolve_image_ref(url) for url in reference_images]
            if len(resolved) == 1:
                body["image"] = resolved[0]
            else:
                body["image"] = resolved
                body["sequential_image_generation"] = "disabled"
            body["watermark"] = False
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=180,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = ""
            try:
                error_payload = _load_json_response(exc.response) if exc.response else {}
                detail = error_payload.get("error", {}).get("message", "") if isinstance(error_payload, dict) else ""
            except Exception:
                pass
            raise ValueError(f"图片生成失败: {detail or exc}") from exc
        payload = _load_json_response(response)
        try:
            item = payload["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Image response missing data[0]") from exc
        image_ref = item.get("url") or item.get("b64_json")
        if not isinstance(image_ref, str) or not image_ref:
            raise ValueError("Image response missing url or b64_json")
        return {"url": image_ref, "raw": payload}

    @staticmethod
    def _resolve_image_ref(url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/api/files/media/"):
            import base64
            from pathlib import Path
            from backend.app.core.config import get_settings
            file_name = url.split("/")[-1]
            local = Path(get_settings().storage_dir) / "media" / file_name
            if local.is_file():
                raw = local.read_bytes()
                ext = local.suffix.lower().lstrip(".")
                mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
                return f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        return url

    def describe_image(
        self,
        *,
        model_config: ModelConfig,
        api_key: str,
        image_url: str,
        instruction: str,
    ) -> str:
        self._validate(model_config=model_config, api_key=api_key)
        endpoint = f"{model_config.base_url.rstrip('/')}/chat/completions"
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_config.model_name,
                "messages": [
                    {"role": "system", "content": "你是小红书图片分析助手。"},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction or "描述这张图片适合的小红书卖点。"},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = _load_json_response(response)
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI response missing choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI image description is empty")
        return content.strip()

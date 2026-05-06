from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings
from backend.app.core.deps import get_current_user
from backend.app.models import User
from backend.app.services.image_util import compose_cover_image, resize_image_file

router = APIRouter(prefix="/files", tags=["files"])


class ComposeImageRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=800)
    width: int = Field(default=1080, ge=320, le=2400)
    height: int = Field(default=1440, ge=320, le=3200)
    background_color: str = Field(default="#fafaf8", max_length=16)
    accent_color: str = Field(default="#111111", max_length=16)


class ResizeImageRequest(BaseModel):
    source_file_name: str = Field(min_length=1, max_length=180)
    width: int = Field(default=1080, ge=128, le=2400)
    height: int = Field(default=1440, ge=128, le=3200)
    mode: Literal["cover", "contain"] = "cover"
    format: Literal["png", "jpeg"] = "png"
    quality: int = Field(default=90, ge=40, le=100)


def _export_media_type(file_name: str) -> str:
    if file_name.endswith(".csv"):
        return "text/csv; charset=utf-8"
    return "application/json"


def _media_dir() -> Path:
    return Path(get_settings().storage_dir) / "media"


def _owner_media_prefix(current_user: User) -> str:
    return f"xhs-image-u{current_user.id}-"


def _validate_owner_media_name(file_name: str, current_user: User) -> str:
    if Path(file_name).name != file_name or ".." in file_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")
    valid_prefixes = (_owner_media_prefix(current_user), f"xhs-asset-u{current_user.id}-", f"xhs-upload-u{current_user.id}-")
    if not file_name.startswith(valid_prefixes):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")
    return file_name


def _media_type(file_name: str) -> str:
    lower = file_name.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".mp4"):
        return "video/mp4"
    if lower.endswith(".mov"):
        return "video/quicktime"
    return "image/png"


def _serialize_media_file(*, file_name: str, width: int, height: int) -> dict:
    return {
        "file_name": file_name,
        "file_path": str(_media_dir() / file_name),
        "download_url": f"/api/files/media/{file_name}",
        "width": width,
        "height": height,
        "media_type": _media_type(file_name),
    }


@router.get("/images")
def list_user_images(current_user: User = Depends(get_current_user)):
    prefix = f"xhs-upload-u{current_user.id}-"
    media_dir = _media_dir()
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    files = []
    if media_dir.is_dir():
        for f in sorted(media_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.name.startswith(prefix) and f.suffix.lower() in image_exts:
                files.append({"file_name": f.name, "url": f"/api/files/media/{f.name}", "size": f.stat().st_size})
    return {"items": files}


@router.delete("/images/{file_name}")
def delete_user_image(file_name: str, current_user: User = Depends(get_current_user)):
    prefix = f"xhs-upload-u{current_user.id}-"
    if Path(file_name).name != file_name or ".." in file_name or not file_name.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    file_path = _media_dir() / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    file_path.unlink()
    return {"file_name": file_name, "status": "deleted"}


@router.post("/images/compose")
def compose_image(payload: ComposeImageRequest, current_user: User = Depends(get_current_user)):
    file_name = f"{_owner_media_prefix(current_user)}{uuid4().hex}.png"
    output_path = _media_dir() / file_name
    compose_cover_image(
        output_path=output_path,
        title=payload.title,
        body=payload.body,
        width=payload.width,
        height=payload.height,
        background_color=payload.background_color,
        accent_color=payload.accent_color,
    )
    return _serialize_media_file(file_name=file_name, width=payload.width, height=payload.height)


@router.post("/images/resize")
def resize_image(payload: ResizeImageRequest, current_user: User = Depends(get_current_user)):
    source_file_name = _validate_owner_media_name(payload.source_file_name, current_user)
    source_path = _media_dir() / source_file_name
    if not source_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")

    extension = "jpg" if payload.format == "jpeg" else "png"
    file_name = f"{_owner_media_prefix(current_user)}{uuid4().hex}.{extension}"
    output_path = _media_dir() / file_name
    resize_image_file(
        source_path=source_path,
        output_path=output_path,
        width=payload.width,
        height=payload.height,
        mode=payload.mode,
        image_format=payload.format,
        quality=payload.quality,
    )
    return _serialize_media_file(file_name=file_name, width=payload.width, height=payload.height)


@router.get("/media/{file_name}")
def download_media(file_name: str):
    if Path(file_name).name != file_name or ".." in file_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")
    file_path = _media_dir() / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")
    return FileResponse(file_path, filename=file_name, media_type=_media_type(file_name))


@router.get("/exports/{file_name}")
def download_export(file_name: str, current_user: User = Depends(get_current_user)):
    if Path(file_name).name != file_name or ".." in file_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found")

    owner_prefixes = (f"xhs-notes-u{current_user.id}-", f"xhs-report-u{current_user.id}-")
    if not file_name.startswith(owner_prefixes):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found")

    export_dir = Path(get_settings().storage_dir) / "exports"
    file_path = export_dir / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found")

    return FileResponse(file_path, filename=file_name, media_type=_export_media_type(file_name))


ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mkv"}
MAX_UPLOAD_SIZE = 100 * 1024 * 1024


@router.post("/upload")
async def upload_file(file: UploadFile, current_user: User = Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的文件格式: {ext}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件大小超过 100MB 限制")

    asset_type = "video" if ext in {".mp4", ".mov", ".avi", ".mkv"} else "image"
    file_name = f"xhs-upload-u{current_user.id}-{uuid4().hex}{ext}"
    media_dir = _media_dir()
    media_dir.mkdir(parents=True, exist_ok=True)
    output_path = media_dir / file_name
    output_path.write_bytes(content)

    return {
        "file_name": file_name,
        "file_path": str(output_path.resolve()),
        "download_url": f"/api/files/media/{file_name}",
        "asset_type": asset_type,
        "size": len(content),
    }

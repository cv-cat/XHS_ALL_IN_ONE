from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def _parse_hex_color(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    value = value.strip()
    if len(value) == 7 and value.startswith("#"):
        try:
            return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
        except ValueError:
            return fallback
    return fallback


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = " ".join(text.strip().split())
    if not text:
        return []

    lines: list[str] = []
    current = ""
    for char in text:
        candidate = f"{current}{char}"
        if current and _text_width(draw, candidate, font) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def compose_cover_image(
    *,
    output_path: Path,
    title: str,
    body: str,
    width: int,
    height: int,
    background_color: str,
    accent_color: str,
) -> None:
    background = _parse_hex_color(background_color, (250, 250, 248))
    accent = _parse_hex_color(accent_color, (17, 17, 17))
    ink = (17, 17, 17)
    muted = (92, 98, 112)

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    margin = max(44, width // 13)
    title_font = _font(max(34, width // 11), bold=True)
    body_font = _font(max(22, width // 28))
    footer_font = _font(max(16, width // 42))

    accent_height = max(10, height // 80)
    draw.rounded_rectangle(
        (margin, margin, width - margin, margin + accent_height),
        radius=accent_height // 2,
        fill=accent,
    )

    y = margin + max(72, height // 12)
    title_lines = _wrap_text(draw, title, title_font, width - margin * 2)[:5]
    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=ink)
        y += int(title_font.size * 1.28) if hasattr(title_font, "size") else 48

    if body.strip():
        y += max(28, height // 34)
        body_lines = _wrap_text(draw, body, body_font, width - margin * 2)[:8]
        for line in body_lines:
            draw.text((margin, y), line, font=body_font, fill=muted)
            y += int(body_font.size * 1.42) if hasattr(body_font, "size") else 34

    footer = "Spider_XHS · XHS cover utility"
    footer_y = height - margin - max(22, height // 60)
    draw.text((margin, footer_y), footer, font=footer_font, fill=muted)
    draw.line((margin, footer_y - 18, width - margin, footer_y - 18), fill=(224, 224, 220), width=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)


def resize_image_file(
    *,
    source_path: Path,
    output_path: Path,
    width: int,
    height: int,
    mode: str,
    image_format: str,
    quality: int,
) -> None:
    with Image.open(source_path) as source:
        image = source.convert("RGB")
        resample = getattr(Image, "Resampling", Image).LANCZOS
        if mode == "contain":
            resized = ImageOps.contain(image, (width, height), method=resample)
            canvas = Image.new("RGB", (width, height), (255, 255, 255))
            left = (width - resized.width) // 2
            top = (height - resized.height) // 2
            canvas.paste(resized, (left, top))
            output = canvas
        else:
            output = ImageOps.fit(image, (width, height), method=resample, centering=(0.5, 0.5))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if image_format == "jpeg":
        output.save(output_path, format="JPEG", quality=quality, optimize=True)
    else:
        output.save(output_path, format="PNG", optimize=True)

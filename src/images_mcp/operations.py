"""Image processing operations powered by Pillow."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps


def get_image_metadata(file_path: str) -> Dict[str, Any]:
    """Retrieve detailed metadata about an image file.

    Args:
        file_path: Absolute or relative path to the image file.

    Returns:
        Dictionary containing image dimensions, format, mode, file size, and EXIF summary.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {file_path}")

    stat = path.stat()
    file_size_bytes = stat.st_size
    file_size_kb = round(file_size_bytes / 1024, 2)

    with Image.open(path) as img:
        width, height = img.size
        format_name = img.format or path.suffix.lstrip(".").upper()
        mode = img.mode
        info = img.info.copy()

    # Extract clean info
    dpi = info.get("dpi")
    if dpi:
        dpi = (round(dpi[0], 2), round(dpi[1], 2))

    return {
        "file_name": path.name,
        "file_path": str(path),
        "format": format_name,
        "width": width,
        "height": height,
        "aspect_ratio": f"{round(width / max(height, 1), 2)}:1",
        "mode": mode,
        "color_channels": len(mode),
        "file_size_bytes": file_size_bytes,
        "file_size_kb": file_size_kb,
        "dpi": dpi,
        "has_transparency": mode in ("RGBA", "LA") or "transparency" in info,
    }


def _determine_output_path(input_path: Path, output_path: Optional[str], suffix_tag: str, ext: Optional[str] = None) -> Path:
    if output_path:
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    
    extension = ext if ext else input_path.suffix
    if not extension.startswith("."):
        extension = f".{extension}"
    return input_path.with_name(f"{input_path.stem}_{suffix_tag}{extension}")


def resize_image(
    file_path: str,
    output_path: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_aspect_ratio: bool = True,
) -> Dict[str, Any]:
    """Resize an image to specific dimensions.

    Args:
        file_path: Source image path.
        output_path: Optional destination path. If not provided, saves alongside source with '_resized'.
        width: Target width in pixels.
        height: Target height in pixels.
        keep_aspect_ratio: If True, preserves aspect ratio fitting inside (width, height).
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {file_path}")
    if width is None and height is None:
        raise ValueError("At least one of width or height must be specified.")

    with Image.open(path) as img:
        orig_w, orig_h = img.size
        
        if keep_aspect_ratio:
            if width and height:
                target_w, target_h = width, height
                ratio = min(target_w / orig_w, target_h / orig_h)
                new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
            elif width:
                ratio = width / orig_w
                new_w, new_h = width, int(orig_h * ratio)
            else:
                assert height is not None
                ratio = height / orig_h
                new_w, new_h = int(orig_w * ratio), height
        else:
            new_w = width if width is not None else orig_w
            new_h = height if height is not None else orig_h

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        out_file = _determine_output_path(path, output_path, f"{new_w}x{new_h}")
        resized.save(out_file)

    return {
        "status": "success",
        "input_path": str(path),
        "output_path": str(out_file),
        "original_dimensions": [orig_w, orig_h],
        "new_dimensions": [new_w, new_h],
        "output_size_kb": round(out_file.stat().st_size / 1024, 2),
    }


def convert_image_format(
    file_path: str,
    target_format: str,
    output_path: Optional[str] = None,
    quality: int = 90,
) -> Dict[str, Any]:
    """Convert an image between formats (e.g. PNG, JPEG, WEBP).

    Args:
        file_path: Source image path.
        target_format: Target format (e.g., 'png', 'jpeg', 'webp').
        output_path: Optional output path.
        quality: Compression quality (1-100) for lossy formats like JPEG/WEBP.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {file_path}")

    fmt_clean = target_format.lower().lstrip(".")
    if fmt_clean == "jpg":
        fmt_clean = "jpeg"

    valid_formats = {"jpeg", "png", "webp", "bmp", "tiff", "gif", "ico"}
    if fmt_clean not in valid_formats:
        raise ValueError(f"Unsupported format '{target_format}'. Supported: {', '.join(sorted(valid_formats))}")

    out_ext = ".jpg" if fmt_clean == "jpeg" else f".{fmt_clean}"
    out_file = _determine_output_path(path, output_path, f"converted", ext=out_ext)

    with Image.open(path) as img:
        # If saving to JPEG, convert RGBA to RGB with white background
        if fmt_clean == "jpeg" and img.mode in ("RGBA", "LA", "P"):
            converted = Image.new("RGB", img.size, (255, 255, 255))
            converted.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        else:
            converted = img.copy()

        save_kwargs: Dict[str, Any] = {}
        if fmt_clean in ("jpeg", "webp"):
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True

        converted.save(out_file, format=fmt_clean.upper(), **save_kwargs)

    return {
        "status": "success",
        "input_path": str(path),
        "output_path": str(out_file),
        "target_format": fmt_clean.upper(),
        "output_size_kb": round(out_file.stat().st_size / 1024, 2),
    }


def crop_image(
    file_path: str,
    left: int,
    top: int,
    right: int,
    bottom: int,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Crop an image to the bounding box (left, top, right, bottom).

    Args:
        file_path: Source image path.
        left: Left pixel coordinate.
        top: Top pixel coordinate.
        right: Right pixel coordinate.
        bottom: Bottom pixel coordinate.
        output_path: Optional destination file path.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {file_path}")

    with Image.open(path) as img:
        orig_w, orig_h = img.size
        if left < 0 or top < 0 or right > orig_w or bottom > orig_h or left >= right or top >= bottom:
            raise ValueError(
                f"Invalid crop coordinates: ({left}, {top}, {right}, {bottom}). Image size is {orig_w}x{orig_h}."
            )

        cropped = img.crop((left, top, right, bottom))
        out_file = _determine_output_path(path, output_path, "cropped")
        cropped.save(out_file)

    return {
        "status": "success",
        "input_path": str(path),
        "output_path": str(out_file),
        "crop_box": [left, top, right, bottom],
        "crop_dimensions": [right - left, bottom - top],
        "output_size_kb": round(out_file.stat().st_size / 1024, 2),
    }


def rotate_flip_image(
    file_path: str,
    angle: float = 0,
    flip_horizontal: bool = False,
    flip_vertical: bool = False,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Rotate and/or flip an image.

    Args:
        file_path: Source image path.
        angle: Angle in degrees to rotate counter-clockwise.
        flip_horizontal: If True, mirrors horizontally.
        flip_vertical: If True, mirrors vertically.
        output_path: Optional output path.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {file_path}")

    with Image.open(path) as img:
        processed = img.copy()
        if angle != 0:
            processed = processed.rotate(angle, expand=True)
        if flip_horizontal:
            processed = ImageOps.mirror(processed)
        if flip_vertical:
            processed = ImageOps.flip(processed)

        out_file = _determine_output_path(path, output_path, "transformed")
        processed.save(out_file)

    return {
        "status": "success",
        "input_path": str(path),
        "output_path": str(out_file),
        "angle": angle,
        "flipped_horizontal": flip_horizontal,
        "flipped_vertical": flip_vertical,
        "dimensions": [processed.width, processed.height],
        "output_size_kb": round(out_file.stat().st_size / 1024, 2),
    }


def apply_image_filter(
    file_path: str,
    filter_type: str,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply an image filter (grayscale, blur, sharpen, contour, edge_enhance, emboss).

    Args:
        file_path: Source image path.
        filter_type: Filter name ('grayscale', 'blur', 'sharpen', 'contour', 'edge_enhance', 'emboss').
        output_path: Optional output path.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {file_path}")

    filt = filter_type.strip().lower()
    with Image.open(path) as img:
        if filt == "grayscale" or filt == "greyscale":
            processed = ImageOps.grayscale(img)
        elif filt == "blur":
            processed = img.filter(ImageFilter.BLUR)
        elif filt == "sharpen":
            processed = img.filter(ImageFilter.SHARPEN)
        elif filt == "contour":
            processed = img.filter(ImageFilter.CONTOUR)
        elif filt == "edge_enhance":
            processed = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
        elif filt == "emboss":
            processed = img.filter(ImageFilter.EMBOSS)
        else:
            valid = ["grayscale", "blur", "sharpen", "contour", "edge_enhance", "emboss"]
            raise ValueError(f"Unknown filter '{filter_type}'. Supported: {', '.join(valid)}")

        out_file = _determine_output_path(path, output_path, filt)
        processed.save(out_file)

    return {
        "status": "success",
        "input_path": str(path),
        "output_path": str(out_file),
        "applied_filter": filt,
        "output_size_kb": round(out_file.stat().st_size / 1024, 2),
    }

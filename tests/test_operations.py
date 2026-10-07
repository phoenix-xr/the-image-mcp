import tempfile
from pathlib import Path
from PIL import Image
import pytest

from images_mcp import operations
from images_mcp.server import server


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    img_path = tmp_path / "test_image.png"
    # Create 200x100 RGBA image
    img = Image.new("RGBA", (200, 100), color=(255, 0, 0, 255))
    img.save(img_path)
    return img_path


def test_get_image_metadata(sample_image: Path):
    meta = operations.get_image_metadata(str(sample_image))
    assert meta["width"] == 200
    assert meta["height"] == 100
    assert meta["format"] == "PNG"
    assert meta["mode"] == "RGBA"
    assert meta["has_transparency"] is True
    assert meta["file_size_bytes"] > 0


def test_resize_image(sample_image: Path, tmp_path: Path):
    out_file = tmp_path / "resized.png"
    res = operations.resize_image(
        file_path=str(sample_image),
        output_path=str(out_file),
        width=100,
        height=50,
        keep_aspect_ratio=False,
    )
    assert res["status"] == "success"
    assert res["new_dimensions"] == [100, 50]
    assert out_file.exists()


def test_convert_image_format(sample_image: Path, tmp_path: Path):
    out_file = tmp_path / "converted.webp"
    res = operations.convert_image_format(
        file_path=str(sample_image),
        target_format="webp",
        output_path=str(out_file),
        quality=85,
    )
    assert res["status"] == "success"
    assert res["target_format"] == "WEBP"
    assert out_file.exists()


def test_crop_image(sample_image: Path, tmp_path: Path):
    out_file = tmp_path / "cropped.png"
    res = operations.crop_image(
        file_path=str(sample_image),
        left=10,
        top=10,
        right=60,
        bottom=40,
        output_path=str(out_file),
    )
    assert res["status"] == "success"
    assert res["crop_dimensions"] == [50, 30]
    assert out_file.exists()


def test_rotate_flip_image(sample_image: Path, tmp_path: Path):
    out_file = tmp_path / "transformed.png"
    res = operations.rotate_flip_image(
        file_path=str(sample_image),
        angle=90,
        flip_horizontal=True,
        output_path=str(out_file),
    )
    assert res["status"] == "success"
    assert res["dimensions"] == [100, 200]
    assert out_file.exists()


def test_apply_image_filter(sample_image: Path, tmp_path: Path):
    out_file = tmp_path / "filtered.png"
    res = operations.apply_image_filter(
        file_path=str(sample_image),
        filter_type="grayscale",
        output_path=str(out_file),
    )
    assert res["status"] == "success"
    assert res["applied_filter"] == "grayscale"
    assert out_file.exists()


@pytest.mark.asyncio
async def test_server_tools_registered():
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_image_metadata" in tool_names
    assert "resize_image" in tool_names
    assert "convert_image_format" in tool_names
    assert "crop_image" in tool_names
    assert "rotate_flip_image" in tool_names
    assert "apply_image_filter" in tool_names
    assert "get_image_low" in tool_names
    assert "download_high_res" in tool_names

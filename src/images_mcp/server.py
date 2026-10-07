"""MCP Server for image processing, conversion, and metadata inspection."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from images_mcp import browser, operations

# Load environment variables
load_dotenv()

# Setup logging to stderr so stdio JSON-RPC transport isn't corrupted
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("images-mcp")

# Initialize MCP server
server = MCPServer(
    name="images-mcp",
    version="0.1.0",
    description="MCP server providing image processing, conversion, cropping, and metadata analysis tools.",
)


@server.resource("images://supported-formats")
def get_supported_formats() -> str:
    """Return JSON string of supported image formats and available filters."""
    info = {
        "formats": ["JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "ICO"],
        "filters": ["grayscale", "blur", "sharpen", "contour", "edge_enhance", "emboss"],
        "max_recommended_dimension": 8192,
    }
    return json.dumps(info, indent=2)


@server.tool(
    name="get_image_metadata",
    description="Get detailed image metadata including dimensions, format, mode, file size, DPI, and transparency.",
)
def get_image_metadata(file_path: str) -> Dict[str, Any]:
    """Retrieve detailed metadata about an image file.

    Args:
        file_path: Path to the image file.
    """
    try:
        return operations.get_image_metadata(file_path)
    except Exception as e:
        logger.error(f"Error reading image metadata for {file_path}: {e}")
        return {"error": str(e), "file_path": file_path}


@server.tool(
    name="resize_image",
    description="Resize an image to specified width and/or height with optional aspect-ratio preservation.",
)
def resize_image(
    file_path: str,
    output_path: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    keep_aspect_ratio: bool = True,
) -> Dict[str, Any]:
    """Resize an image.

    Args:
        file_path: Path to the input image file.
        output_path: Optional destination file path. If omitted, saves beside input with dimension suffix.
        width: Desired width in pixels (e.g., 800).
        height: Desired height in pixels (e.g., 600).
        keep_aspect_ratio: Whether to preserve original aspect ratio (defaults to True).
    """
    try:
        return operations.resize_image(
            file_path=file_path,
            output_path=output_path,
            width=width,
            height=height,
            keep_aspect_ratio=keep_aspect_ratio,
        )
    except Exception as e:
        logger.error(f"Error resizing image {file_path}: {e}")
        return {"error": str(e), "file_path": file_path}


@server.tool(
    name="convert_image_format",
    description="Convert an image to a different format such as PNG, JPEG, WEBP, BMP, or TIFF.",
)
def convert_image_format(
    file_path: str,
    target_format: str,
    output_path: Optional[str] = None,
    quality: int = 90,
) -> Dict[str, Any]:
    """Convert an image format.

    Args:
        file_path: Path to the input image file.
        target_format: Target format (e.g., 'png', 'jpeg', 'webp').
        output_path: Optional output file path.
        quality: Quality level from 1 to 100 for lossy formats (default: 90).
    """
    try:
        return operations.convert_image_format(
            file_path=file_path,
            target_format=target_format,
            output_path=output_path,
            quality=quality,
        )
    except Exception as e:
        logger.error(f"Error converting image {file_path}: {e}")
        return {"error": str(e), "file_path": file_path}


@server.tool(
    name="crop_image",
    description="Crop an image using bounding box pixel coordinates [left, top, right, bottom].",
)
def crop_image(
    file_path: str,
    left: int,
    top: int,
    right: int,
    bottom: int,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Crop an image.

    Args:
        file_path: Path to the input image file.
        left: Left pixel boundary.
        top: Top pixel boundary.
        right: Right pixel boundary.
        bottom: Bottom pixel boundary.
        output_path: Optional destination path.
    """
    try:
        return operations.crop_image(
            file_path=file_path,
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            output_path=output_path,
        )
    except Exception as e:
        logger.error(f"Error cropping image {file_path}: {e}")
        return {"error": str(e), "file_path": file_path}


@server.tool(
    name="rotate_flip_image",
    description="Rotate by an angle (counter-clockwise) and/or mirror horizontally or vertically.",
)
def rotate_flip_image(
    file_path: str,
    angle: float = 0,
    flip_horizontal: bool = False,
    flip_vertical: bool = False,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Rotate and/or flip an image.

    Args:
        file_path: Path to the input image.
        angle: Degrees to rotate counter-clockwise.
        flip_horizontal: Whether to mirror horizontally.
        flip_vertical: Whether to flip vertically.
        output_path: Optional destination path.
    """
    try:
        return operations.rotate_flip_image(
            file_path=file_path,
            angle=angle,
            flip_horizontal=flip_horizontal,
            flip_vertical=flip_vertical,
            output_path=output_path,
        )
    except Exception as e:
        logger.error(f"Error rotating/flipping image {file_path}: {e}")
        return {"error": str(e), "file_path": file_path}


@server.tool(
    name="apply_image_filter",
    description="Apply visual filters: grayscale, blur, sharpen, contour, edge_enhance, or emboss.",
)
def apply_image_filter(
    file_path: str,
    filter_type: str,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply a visual filter to an image.

    Args:
        file_path: Path to the input image.
        filter_type: One of 'grayscale', 'blur', 'sharpen', 'contour', 'edge_enhance', 'emboss'.
        output_path: Optional destination path.
    """
    try:
        return operations.apply_image_filter(
            file_path=file_path,
            filter_type=filter_type,
            output_path=output_path,
        )
    except Exception as e:
        logger.error(f"Error filtering image {file_path}: {e}")
        return {"error": str(e), "file_path": file_path}


@server.tool(
    name="get_image_low",
    description="Search images for a query via browser automation. Returns structured candidates with titles, low-res thumbnails, and high-res URLs for LLM inspection. Set download=True to save low-res thumbnails locally.",
)
async def get_image_low(
    query: str,
    download: bool = False,
    max_results: int = 5,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Search images and return candidate previews.

    Args:
        query: Search term (e.g., 'beautifulsoup python logo', 'nature wallpaper').
        download: Whether to download low-res thumbnails locally (default: False).
        max_results: Number of image candidates to return (default: 5).
        output_dir: Directory to save thumbnails if download=True.
    """
    try:
        return await browser.search_and_get_images(
            query=query,
            max_results=max_results,
            download=download,
            download_count=max_results if download else None,
            resolution="thumbnail",
            output_dir=output_dir,
        )
    except Exception as e:
        logger.error(f"Error in get_image_low for '{query}': {e}")
        return {"error": str(e), "query": query, "status": "error"}


@server.tool(
    name="download_high_res",
    description="Download and store a high-resolution image from its URL (obtained from get_image_low) to disk with format and dimensions verification.",
)
async def download_high_res(
    url: str,
    output_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    filename_prefix: str = "highres",
    page_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Download and store a high-resolution image.

    Args:
        url: High-resolution image URL (the 'highres_url' from get_image_low).
        output_path: Optional exact output file path (e.g., './my_photo.png').
        output_dir: Optional folder where the image should be saved if output_path is not specified.
        filename_prefix: Prefix for the generated filename.
        page_url: Optional referrer URL to bypass anti-hotlinking protections.
    """
    try:
        return await browser.download_image_to_disk(
            image_url=url,
            output_path=output_path,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            page_url=page_url,
        )
    except Exception as e:
        logger.error(f"Error in download_high_res from {url}: {e}")
        return {"error": str(e), "url": url, "status": "error"}



def main():
    """Run the MCP server over stdio."""
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    logger.info(f"Starting images-mcp server with {transport} transport...")
    server.run(transport=transport)


if __name__ == "__main__":
    main()

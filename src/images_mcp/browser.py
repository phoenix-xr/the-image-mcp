"""CDP-based lightweight browser automation for image search using pre-installed Chrome/Edge."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image
import websockets

logger = logging.getLogger("images-mcp.browser")

BROWSER_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def find_system_browser() -> Path:
    """Find local Google Chrome or Microsoft Edge executable."""
    for path in BROWSER_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError("Neither Google Chrome nor Microsoft Edge was found on system.")


async def _execute_cdp_search(
    browser_exe: Path,
    query: str,
    max_results: int = 10,
    prefer_direct_path: bool = False,
) -> Dict[str, Any]:
    """Perform Google Search, click 'Images' tab (or direct path), and extract image items."""
    encoded_query = urllib.parse.quote_plus(query)
    temp_dir = tempfile.mkdtemp(prefix="mcp_img_search_")
    
    import socket
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    cmd = [
        str(browser_exe),
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={temp_dir}",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--lang=en-US",
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(35):
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
                    if r.status_code == 200:
                        ws_url = r.json().get("webSocketDebuggerUrl")
                        break
            except Exception:
                await asyncio.sleep(0.15)

        if not ws_url:
            raise RuntimeError(f"Could not connect to {browser_exe.name} CDP port {port}")

        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": "about:blank"}}))
            target_resp = json.loads(await ws.recv())
            target_id = target_resp["result"]["targetId"]

        async with httpx.AsyncClient() as client:
            targets = (await client.get(f"http://127.0.0.1:{port}/json")).json()
            page_target = next(t for t in targets if t["id"] == target_id)
            page_ws_url = page_target["webSocketDebuggerUrl"]

        async with websockets.connect(page_ws_url, max_size=50 * 1024 * 1024) as page_ws:
            msg_id = 10

            async def send_cmd(method: str, params: dict = None) -> dict:
                nonlocal msg_id
                msg_id += 1
                curr_id = msg_id
                payload = {"id": curr_id, "method": method}
                if params:
                    payload["params"] = params
                await page_ws.send(json.dumps(payload))
                while True:
                    raw = await page_ws.recv()
                    data = json.loads(raw)
                    if data.get("id") == curr_id:
                        return data

            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")

            start_url = (
                f"https://www.google.com/search?q={encoded_query}&tbm=isch"
                if prefer_direct_path
                else f"https://www.google.com/search?q={encoded_query}"
            )
            logger.info(f"Navigating to {start_url}...")
            await send_cmd("Page.navigate", {"url": start_url})
            await asyncio.sleep(3.0)

            # Check if blocked by captcha
            check_url_js = "window.location.href"
            res = await send_cmd("Runtime.evaluate", {"expression": check_url_js, "returnByValue": True})
            current_url = res.get("result", {}).get("result", {}).get("value", "")

            clicked_images_tab = False
            if "/sorry/index" not in current_url and not prefer_direct_path:
                click_js = """
                (() => {
                    const links = Array.from(document.querySelectorAll('a'));
                    const imgLink = links.find(a => {
                        const txt = (a.innerText || a.textContent || '').trim().toLowerCase();
                        const aria = (a.getAttribute('aria-label') || '').trim().toLowerCase();
                        return txt === 'images' || aria === 'images';
                    });
                    if (imgLink) {
                        const href = imgLink.href;
                        imgLink.click();
                        return { found: true, href: href };
                    }
                    return { found: false };
                })()
                """
                click_res = await send_cmd("Runtime.evaluate", {"expression": click_js, "returnByValue": True})
                click_data = click_res.get("result", {}).get("result", {}).get("value", {})
                clicked_images_tab = click_data.get("found", False)
                if clicked_images_tab:
                    await asyncio.sleep(3.0)

            # Extract both thumbnails and high-res script URLs from Google
            extract_js = f"""
            (() => {{
                const items = [];
                const seen = new Set();
                
                // Parse scripts for high-res image URLs
                const scripts = Array.from(document.querySelectorAll('script')).map(s => s.textContent || '');
                let highresPool = [];
                for (const s of scripts) {{
                    if (s.includes('http') && (s.includes('.png') || s.includes('.jpg') || s.includes('.jpeg') || s.includes('.webp'))) {{
                        const matches = s.match(/(https?:\\/\\/[^"\'\\s\\\\]+\\.(?:png|jpe?g|webp))/gi);
                        if (matches) {{
                            for (const m of matches) {{
                                if (!m.includes('gstatic.com') && !m.includes('google.com') && !seen.has(m)) {{
                                    highresPool.push(m);
                                }}
                            }}
                        }}
                    }}
                }}

                const imgs = Array.from(document.querySelectorAll('img, [role="img"]'));
                let idx = 0;
                for (const img of imgs) {{
                    let thumb = img.src || img.dataset.src || img.dataset.iurl || img.getAttribute('src') || '';
                    if (!thumb || thumb.startsWith('data:image/svg') || thumb.includes('favicon') || thumb.includes('cleardot')) continue;
                    if (seen.has(thumb)) continue;
                    seen.add(thumb);
                    
                    const alt = img.alt || img.getAttribute('aria-label') || img.title || '';
                    const highres = (idx < highresPool.length) ? highresPool[idx] : thumb;
                    idx++;

                    items.push({{
                        id: items.length + 1,
                        title: alt || 'Image result',
                        thumbnail_url: thumb,
                        highres_url: highres,
                        page_url: window.location.href,
                        width: img.naturalWidth || img.width || 0,
                        height: img.naturalHeight || img.height || 0
                    }});
                    if (items.length >= {max_results}) break;
                }}
                return {{
                    url: window.location.href,
                    title: document.title,
                    images: items
                }};
            }})()
            """
            eval_res = await send_cmd("Runtime.evaluate", {"expression": extract_js, "returnByValue": True})
            page_data = eval_res.get("result", {}).get("result", {}).get("value", {})
            images = page_data.get("images", [])

            is_blocked = "/sorry/index" in page_data.get("url", "") or len(images) == 0

            return {
                "source": "google",
                "clicked_images_tab": clicked_images_tab,
                "current_url": page_data.get("url", ""),
                "page_title": page_data.get("title", ""),
                "is_blocked": is_blocked,
                "images": images,
            }

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


async def _execute_bing_search(browser_exe: Path, query: str, max_results: int = 10) -> Dict[str, Any]:
    """Search images using Bing, extracting both high-res (murl) and thumbnail (turl) URLs."""
    encoded_query = urllib.parse.quote_plus(query)
    temp_dir = tempfile.mkdtemp(prefix="mcp_bing_")
    
    import socket
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    cmd = [
        str(browser_exe),
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={temp_dir}",
        "--disable-gpu",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(30):
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
                    if r.status_code == 200:
                        ws_url = r.json().get("webSocketDebuggerUrl")
                        break
            except Exception:
                await asyncio.sleep(0.15)

        if not ws_url:
            return {"source": "bing", "images": []}

        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": "about:blank"}}))
            target_id = (json.loads(await ws.recv()))["result"]["targetId"]

        async with httpx.AsyncClient() as client:
            targets = (await client.get(f"http://127.0.0.1:{port}/json")).json()
            page_ws_url = next(t["webSocketDebuggerUrl"] for t in targets if t["id"] == target_id)

        async with websockets.connect(page_ws_url, max_size=50 * 1024 * 1024) as page_ws:
            msg_id = 10

            async def send_cmd(method: str, params: dict = None) -> dict:
                nonlocal msg_id
                msg_id += 1
                curr_id = msg_id
                payload = {"id": curr_id, "method": method}
                if params:
                    payload["params"] = params
                await page_ws.send(json.dumps(payload))
                while True:
                    raw = await page_ws.recv()
                    data = json.loads(raw)
                    if data.get("id") == curr_id:
                        return data

            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")

            url = f"https://www.bing.com/images/search?q={encoded_query}"
            await send_cmd("Page.navigate", {"url": url})
            await asyncio.sleep(3.0)

            # In Bing Images, every result container 'a.iusc' contains metadata JSON with 'murl' (highres), 'turl' (thumb), 't' (title), and 'purl' (source page)
            extract_js = f"""
            (() => {{
                const items = [];
                const seen = new Set();
                const links = Array.from(document.querySelectorAll('a.iusc, .imgpt a'));
                for (const a of links) {{
                    const mAttr = a.getAttribute('m');
                    if (mAttr) {{
                        try {{
                            const meta = JSON.parse(mAttr);
                            const highres = meta.murl || '';
                            const thumb = meta.turl || '';
                            if (!highres || seen.has(highres)) continue;
                            seen.add(highres);
                            
                            items.push({{
                                id: items.length + 1,
                                title: meta.t || meta.desc || 'Image result',
                                thumbnail_url: thumb,
                                highres_url: highres,
                                page_url: meta.purl || '',
                                width: 0,
                                height: 0
                            }});
                            if (items.length >= {max_results}) break;
                        }} catch (e) {{}}
                    }}
                }}
                return {{ url: window.location.href, title: document.title, images: items }};
            }})()
            """
            res = await send_cmd("Runtime.evaluate", {"expression": extract_js, "returnByValue": True})
            data = res.get("result", {}).get("result", {}).get("value", {})
            return {
                "source": "bing_search",
                "current_url": data.get("url", ""),
                "page_title": data.get("title", ""),
                "images": data.get("images", []),
            }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


async def download_image_to_disk(
    image_url: str,
    output_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    filename_prefix: str = "image",
    page_url: Optional[str] = None,
    fallback_thumbnail_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Download an image from a URL, with automatic fallback and format validation.

    Args:
        image_url: Target image URL (typically highres_url).
        output_path: Optional exact output file path.
        filename_prefix: Prefix for generated file name.
        page_url: Referer URL to bypass anti-hotlinking protections.
        fallback_thumbnail_url: Fallback thumbnail URL if highres URL is protected/forbidden.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    if page_url:
        headers["Referer"] = page_url

    content = None
    used_url = image_url

    # Attempt primary URL (high-res)
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            r = await client.get(image_url, headers=headers)
            if r.status_code == 200 and len(r.content) > 500:
                content = r.content
        except Exception as e:
            logger.debug(f"High-res download failed for {image_url}: {e}")

        # If primary failed and fallback provided, try thumbnail
        if not content and fallback_thumbnail_url:
            try:
                r_fallback = await client.get(fallback_thumbnail_url, headers=headers)
                if r_fallback.status_code == 200 and len(r_fallback.content) > 500:
                    content = r_fallback.content
                    used_url = fallback_thumbnail_url
            except Exception as e:
                logger.debug(f"Fallback download failed for {fallback_thumbnail_url}: {e}")

    if not content:
        raise ValueError(f"Failed to download image from {image_url}")

    # Determine extension and validate with Pillow
    import io
    with Image.open(io.BytesIO(content)) as img:
        fmt = (img.format or "JPEG").lower()
        width, height = img.size
    
    ext = f".{fmt}"
    if fmt == "jpeg":
        ext = ".jpg"

    if output_path:
        target_file = Path(output_path).resolve()
        target_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        save_folder = Path(output_dir).resolve() if output_dir else Path.cwd() / "downloaded_images"
        save_folder.mkdir(parents=True, exist_ok=True)
        clean_name = re.sub(r"[^\w\-]", "_", filename_prefix.lower())[:35]
        existing_count = len(list(save_folder.glob(f"{clean_name}*"))) + 1
        target_file = save_folder / f"{clean_name}_{existing_count}{ext}"

    target_file.write_bytes(content)

    return {
        "status": "success",
        "file_path": str(target_file),
        "source_url": used_url,
        "is_highres": used_url == image_url,
        "format": fmt.upper(),
        "width": width,
        "height": height,
        "file_size_bytes": len(content),
        "file_size_kb": round(len(content) / 1024, 2),
    }


async def search_and_get_images(
    query: str,
    max_results: int = 5,
    download: bool = False,
    download_count: Optional[int] = None,
    resolution: str = "highres",
    output_dir: Optional[str] = None,
    prefer_direct_path: bool = False,
) -> Dict[str, Any]:
    """Search for images, providing both thumbnails and high-res URLs for LLM selection.

    Args:
        query: Search query (e.g. 'beautifulsoup logo', 'nature wallpaper').
        max_results: Total image candidates to return.
        download: Whether to download images locally.
        download_count: Number of images to download if download=True (defaults to max_results).
        resolution: 'highres' (default) or 'thumbnail'.
        output_dir: Directory where downloaded images should be saved.
        prefer_direct_path: If True, uses direct &tbm=isch URL path instead of clicking tab.
    """
    browser_exe = find_system_browser()
    logger.info(f"Searching images for '{query}' using {browser_exe.name}...")

    # Step 1: Attempt Google
    result = await _execute_cdp_search(
        browser_exe=browser_exe,
        query=query,
        max_results=max_results,
        prefer_direct_path=prefer_direct_path,
    )

    # Step 2: If Google blocked by captcha or 0 images, use Bing search
    if result.get("is_blocked") or not result.get("images"):
        logger.warning("Google Search hit rate-limit. Using fallback high-res image search provider...")
        fallback = await _execute_bing_search(browser_exe, query, max_results=max_results)
        if fallback.get("images"):
            result = fallback
            result["note"] = "Google Search hit bot-protection; retrieved via Bing Images with full-resolution URLs."

    images = result.get("images", [])
    downloaded_files: List[str] = []

    # Step 3: If download is requested, download up to download_count images
    if download and images:
        num_to_download = download_count if download_count is not None else len(images)
        num_to_download = min(num_to_download, len(images))
        clean_prefix = re.sub(r"[^\w\-]", "_", query.lower())[:30]

        for i in range(num_to_download):
            img = images[i]
            target_url = img.get("highres_url") if resolution == "highres" else img.get("thumbnail_url")
            fallback_url = img.get("thumbnail_url") if resolution == "highres" else None
            page_url = img.get("page_url")

            try:
                dl_result = await download_image_to_disk(
                    image_url=target_url or fallback_url,
                    output_dir=output_dir,
                    filename_prefix=f"{clean_prefix}_{i+1}",
                    page_url=page_url,
                    fallback_thumbnail_url=fallback_url,
                )
                img["local_path"] = dl_result["file_path"]
                img["width"] = dl_result["width"]
                img["height"] = dl_result["height"]
                downloaded_files.append(dl_result["file_path"])
            except Exception as e:
                logger.warning(f"Could not download candidate #{i+1}: {e}")

    return {
        "status": "success" if images else "no_images_found",
        "query": query,
        "source": result.get("source", "google"),
        "total_found": len(images),
        "downloaded_files": downloaded_files,
        "images": images,
    }

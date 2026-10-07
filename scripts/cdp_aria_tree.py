"""Extract native browser Accessibility (ARIA) Tree using system Edge or Chrome via CDP.

No Playwright or external browser download required. Uses pre-installed Chromium.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import httpx
import websockets

BROWSER_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def find_browser() -> Path:
    for p in BROWSER_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError("Neither Google Chrome nor Microsoft Edge was found on system.")


class FormattedAXNode:
    def __init__(self, role: str, name: str = "", value: str = "", level: Optional[int] = None):
        self.role = role
        self.name = name.strip()
        self.value = value.strip()
        self.level = level
        self.children: List[FormattedAXNode] = []

    def format_tree(self, depth: int = 0) -> List[str]:
        indent = "  " * depth
        attrs = []
        if self.name:
            clean_name = re.sub(r"\s+", " ", self.name)
            if len(clean_name) > 120:
                clean_name = clean_name[:117] + "..."
            attrs.append(f'"{clean_name}"')
        if self.level is not None:
            attrs.append(f"[level: {self.level}]")
        if self.value:
            attrs.append(f'[value: "{self.value}"]')

        attr_str = (" " + " ".join(attrs)) if attrs else ""
        lines = [f"{indent}- {self.role}{attr_str}"]
        for child in self.children:
            lines.extend(child.format_tree(depth + 1))
        return lines


def build_hierarchical_tree(raw_nodes: List[Dict[str, Any]]) -> FormattedAXNode:
    node_map = {n["nodeId"]: n for n in raw_nodes}
    
    # Find root
    root_raw = next(
        (n for n in raw_nodes if n.get("role", {}).get("value") in ("RootWebArea", "WebArea")),
        raw_nodes[0] if raw_nodes else None
    )
    if not root_raw:
        return FormattedAXNode(role="root", name="Empty Tree")

    def convert_node(raw: Dict[str, Any]) -> List[FormattedAXNode]:
        ignored = raw.get("ignored", False)
        role = raw.get("role", {}).get("value", "generic")
        name = raw.get("name", {}).get("value", "")
        value = raw.get("value", {}).get("value", "")
        
        # Extract level from properties
        level = None
        props = raw.get("properties", [])
        for p in props:
            if p.get("name") == "level":
                level = p.get("value", {}).get("value")

        # Recursively process children
        child_ids = raw.get("childIds", [])
        children: List[FormattedAXNode] = []
        for cid in child_ids:
            if cid in node_map:
                children.extend(convert_node(node_map[cid]))

        # Normalize role names
        if role == "RootWebArea":
            role = "document"
        elif role == "StaticText":
            role = "text"
        elif role == "SearchBox":
            role = "searchbox"
        elif role == "TextField":
            role = "textbox"

        # If node is marked ignored by accessibility engine
        if ignored:
            # Pass through meaningful children
            return children

        # If it's a generic container without name, collapse/hoist its children
        if role in ("generic", "none", "InlineTextBox", "LineBreak", "paragraph") and not name and not value:
            return children

        # If it's pure text identical to parent's name, skip redundant child
        if role == "text" and not name:
            return []

        formatted = FormattedAXNode(role=role, name=str(name) if name else "", value=str(value) if value else "", level=level)
        formatted.children = children
        return [formatted]

    res = convert_node(root_raw)
    return res[0] if res else FormattedAXNode(role="document", name="Empty")


async def extract_cdp_aria_tree(url: str, output_path: Path) -> Path:
    browser_exe = find_browser()
    print(f"Using system browser: {browser_exe}")

    temp_dir = tempfile.mkdtemp(prefix="cdp_aria_")
    port = 9222

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

    print("Launching headless browser process...")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        # Wait for CDP endpoint
        ws_url = None
        for _ in range(40):
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
                    if r.status_code == 200:
                        ws_url = r.json().get("webSocketDebuggerUrl")
                        break
            except Exception:
                await asyncio.sleep(0.15)

        if not ws_url:
            raise RuntimeError("Could not connect to browser CDP port.")

        # Create target
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": "about:blank"}}))
            resp = json.loads(await ws.recv())
            target_id = resp["result"]["targetId"]

        # Get page websocket URL
        async with httpx.AsyncClient() as client:
            targets = (await client.get(f"http://127.0.0.1:{port}/json")).json()
            page_target = next(t for t in targets if t["id"] == target_id)
            page_ws_url = page_target["webSocketDebuggerUrl"]

        async with websockets.connect(page_ws_url, max_size=50 * 1024 * 1024) as page_ws:
            msg_id = 10

            async def send_cmd(method: str, params: dict = None):
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
            await send_cmd("Accessibility.enable")

            print(f"Navigating to {url}...")
            await send_cmd("Page.navigate", {"url": url})

            # Wait for search results to render
            print("Waiting for page rendering and JS execution...")
            await asyncio.sleep(3.5)

            print("Querying Accessibility.getFullAXTree...")
            ax_resp = await send_cmd("Accessibility.getFullAXTree")
            raw_nodes = ax_resp.get("result", {}).get("nodes", [])
            print(f"Retrieved {len(raw_nodes)} raw accessibility nodes.")

            tree = build_hierarchical_tree(raw_nodes)
            lines = tree.format_tree()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            header = [
                f"# ARIA Accessibility Tree Snapshot (Native Browser Engine)",
                f"# URL: {url}",
                f"# Browser: {browser_exe.name} via Chrome DevTools Protocol (CDP)",
                f"# Total Hierarchical Nodes: {len(lines)} (from {len(raw_nodes)} raw AXNodes)",
                f"# Method: Option 1 (System Browser CDP - 0 Playwright dependency)",
                "=" * 80,
                "",
            ]
            full_content = "\n".join(header + lines)
            output_path.write_text(full_content, encoding="utf-8")
            print(f"Saved complete native ARIA tree to {output_path} ({len(lines)} lines)")
            return output_path

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    target_url = "https://www.google.com/search?q=beautifulsoup"
    out_file = Path("aria_tree_google_search_cdp.txt")
    asyncio.run(extract_cdp_aria_tree(target_url, out_file))

# 🖼️ the-image-mcp

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/MCP-Protocol-8A2BE2?style=for-the-badge&logo=anthropic&logoColor=white" alt="MCP" />
  <img src="https://img.shields.io/badge/uv-Astral-22C55E?style=for-the-badge&logo=astral&logoColor=white" alt="uv" />
  <img src="https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge" alt="License: MIT" />
</p>

> **A simple MCP server for AI models to find, preview, download, and edit pictures from the web.**  
> Powered by Chrome DevTools Protocol (CDP) and Pillow. Zero Playwright bloat.


## ⚡ What does it do?

### 1. 🔍 Search & Preview
Searches the web (**Google Images** with automatic **Bing** fallback) and hands low-res thumbnails to the AI so it can inspect candidate images, compare options, and pick the winner.

### 2. 🚀 Grab Full Resolution
Takes the chosen candidate's URL and downloads the crystal-clear, uncompressed original picture (up to 4K+) directly to disk.

### 3. 🛠️ Edit & Transform
| Tool | What it does |
|:---|:---|
| `resize_image` | Resize by width or height while keeping aspect ratio |
| `crop_image` | Cut out any exact bounding box (`left`, `top`, `right`, `bottom`) |
| `convert_image_format` | Convert between **PNG**, **JPEG**, **WEBP**, **BMP**, **TIFF** |
| `rotate_flip_image` | Rotate by any angle or mirror horizontally / vertically |
| `apply_image_filter` | Apply `blur`, `grayscale`, `sharpen`, `contour`, or `edge_enhance` |
| `get_image_metadata` | Inspect dimensions, DPI, color mode, transparency, and file size |

---

## 🚀 Quick Setup

### 1. Install & Run
Make sure you have [uv](https://docs.astral.sh/uv/) installed:

```bash
# Clone and enter the project
git clone https://github.com/phoenix-xr/the-image-mcp.git
cd the-image-mcp

# Sync dependencies
uv sync

# Start the server
uv run images-mcp
```

---

### 2. Connect to Your AI (Claude, Antigravity, Cursor)

Add this block to your `mcp_config.json` or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "the-image-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\anshy\\Documents\\project-gits\\images-mcp",
        "run",
        "images-mcp"
      ]
    }
  }
}
```

---


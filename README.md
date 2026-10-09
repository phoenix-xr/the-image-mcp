# 🖼️ the-image-mcp

[![Listed on mcpservers.org](https://mcpservers.org/badge.svg)](https://mcpservers.org/servers/phoenix-xr/the-image-mcp)

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

## 🚀 Quick Setup (Zero-Friction)

No cloning, building, or manual directory configuration required! Uses [`uvx`](https://docs.astral.sh/uv/) to run directly from GitHub.

### 🤖 Universal AI Setup Prompt

[![Copy Prompt](https://img.shields.io/badge/📋%20Copy%20Prompt-Universal%20AI%20Setup-2563EB?style=for-the-badge)](#-universal-ai-setup-prompt)

> [!TIP]
> **Click the copy icon (📋) in the top-right corner of the code block below**, then paste it directly into your AI chat (**Antigravity**, **Claude Code**, or **Cursor**). The agent will automatically detect its environment and configure the MCP server!

```text
Configure and register the MCP server `the-image-mcp` in your environment:
- If running in Antigravity: add "the-image-mcp" to `~/.gemini/config/mcp_config.json` with command "uvx" and args ["--from", "git+https://github.com/phoenix-xr/the-image-mcp", "images-mcp"].
- If running in Claude Code: execute `claude mcp add the-image-mcp -- uvx --from git+https://github.com/phoenix-xr/the-image-mcp images-mcp`.
- If running in Cursor / Claude Desktop / Windsurf: add "the-image-mcp" to your mcpServers config with command "uvx" and args ["--from", "git+https://github.com/phoenix-xr/the-image-mcp", "images-mcp"].
Confirm once the MCP server is configured and ready to use.
```

---

### ⚙️ 2. Universal Config (Claude Desktop, Cursor, Antigravity)

Add this snippet to your `mcp_config.json` or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "the-image-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/phoenix-xr/the-image-mcp",
        "images-mcp"
      ]
    }
  }
}
```

---

### 💻 3. Local Development (Optional)

```bash
git clone https://github.com/phoenix-xr/the-image-mcp.git
cd the-image-mcp
uv sync
uv run images-mcp
```



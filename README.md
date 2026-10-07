# the-image-mcp

A dead-simple MCP server for AI models to find, download, and edit pictures from the web.

---

## What does it do?

1. Searches the web (**Google Images** with **Bing** fallback) for pictures matching your query. Gives the AI low-res thumbnails to quickly see options and pick the best one.
2. Downloads the crystal-clear, full-size original picture to your computer.
3. **Edit images**:
   - `resize_image`: Change image width/height.
   - `crop_image`: Cut out a specific box from an image.
   - `convert_image_format`: Turn PNGs into JPGs, WEBPs, etc.
   - `rotate_flip_image`: Turn or flip photos.
   - `apply_image_filter`: Add blur, grayscale, sharpen, or edge filters.
   - `get_image_metadata`: Check dimensions, format, and file size.

---

## How to use it

### 1. Install & Run
Make sure you have [uv](https://docs.astral.sh/uv/) installed, then run:

```bash
# Install dependencies
uv sync

# Run the server
uv run images-mcp
```

### 2. Connect to your AI (Claude, Antigravity, Cursor)
Add this to your MCP settings file:

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

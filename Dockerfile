FROM python:3.12-slim

# Install system dependencies (Chromium for CDP browser search)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy project specification files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies using uv
RUN uv sync --frozen || uv sync

ENV PATH="/app/.venv/bin:$PATH"
ENV MCP_TRANSPORT="stdio"

# Default run command
ENTRYPOINT ["images-mcp"]

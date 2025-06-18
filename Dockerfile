# Multi-stage build for lightweight production image
FROM python:3.12-slim AS builder

# Install uv for fast Python dependency management
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# Install dependencies and build package
RUN uv pip install --system --no-cache .

# Production stage
FROM python:3.12-slim

# Create non-root user for security
RUN useradd -m -u 1000 zulipuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY src/ ./src/

# Switch to non-root user
USER zulipuser

# Expose MCP server port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.zulipchat_mcp.config import ConfigManager; ConfigManager().validate_config()" || exit 1

# Default command - run MCP server
CMD ["python", "-m", "src.zulipchat_mcp.server", "server"]
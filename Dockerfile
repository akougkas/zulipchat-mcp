# Multi-stage build for lightweight production image
FROM python:3.12-alpine AS builder

# Install build dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev

# Install uv for fast Python dependency management
RUN pip install --no-cache-dir uv==0.5.11

WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# Install dependencies with all deps
RUN uv pip install --system --no-cache .

# Production stage - use alpine for smaller size
FROM python:3.12-alpine

# Install runtime dependencies only
RUN apk add --no-cache libffi

# Create non-root user for security
RUN adduser -D -u 1000 zulipuser

# Copy Python installation from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY --chown=zulipuser:zulipuser src/ /app/src/

WORKDIR /app

# Switch to non-root user
USER zulipuser

# Expose MCP server port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.zulipchat_mcp.config import ConfigManager; ConfigManager().validate_config()" || exit 1

# Default command - run MCP server
CMD ["python", "-m", "src.zulipchat_mcp.server", "server"]
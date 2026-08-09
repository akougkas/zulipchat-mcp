"""Tests for core/llm.py - the server-side LLM provider that replaced MCP sampling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.zulipchat_mcp.core import llm
from src.zulipchat_mcp.core.llm import LLMUnavailableError, generate, llm_available


class TestLLMAvailability:
    def test_unavailable_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert llm_available() is False

    def test_available_with_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        assert llm_available() is True


class TestGenerate:
    @pytest.mark.asyncio
    async def test_uses_default_model_and_budget(self, monkeypatch):
        """Guards against the default rotting into a retired model ID."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "ok"
        message = MagicMock()
        message.content = [text_block]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=message)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            await generate("hi")

        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-opus-5"
        # Current models think by default; the budget covers thinking + text.
        assert kwargs["max_tokens"] >= 8192

    @pytest.mark.asyncio
    async def test_raises_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(LLMUnavailableError, match="ANTHROPIC_API_KEY"):
            await generate("hello")

    @pytest.mark.asyncio
    async def test_extracts_text_block(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "  generated insight  "
        message = MagicMock()
        message.content = [text_block]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=message)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = await generate("analyze this")

        assert result == "generated insight"
        mock_client.messages.create.assert_called_once()
        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["messages"] == [{"role": "user", "content": "analyze this"}]

    @pytest.mark.asyncio
    async def test_uses_env_model_override(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "ok"
        message = MagicMock()
        message.content = [text_block]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=message)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            await generate("hi")

        assert (
            mock_client.messages.create.call_args.kwargs["model"] == "claude-haiku-4-5"
        )

    @pytest.mark.asyncio
    async def test_empty_text_raises(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        message = MagicMock()
        message.content = []

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=message)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            with pytest.raises(LLMUnavailableError, match="no text content"):
                await generate("hi")

    def test_extract_text_skips_non_text_blocks(self):
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "real text"
        message = MagicMock()
        message.content = [tool_block, text_block]

        assert llm._extract_text(message) == "real text"

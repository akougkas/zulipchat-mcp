"""Tests for server entrypoint CLI behavior."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from src.zulipchat_mcp import server


@pytest.fixture
def mock_config_manager():
    """Config manager fixture that exits early from main."""
    cfg = MagicMock()
    cfg.validate_config.return_value = False
    return cfg


def test_debug_flag_sets_debug_logging_level(mock_config_manager):
    """--debug should configure structured logging at DEBUG level."""
    with (
        patch("src.zulipchat_mcp.server.setup_structured_logging") as mock_setup,
        patch("src.zulipchat_mcp.server.get_logger") as mock_get_logger,
        patch("src.zulipchat_mcp.server.init_config_manager") as mock_init_cfg,
        patch.object(sys, "argv", ["zulipchat-mcp", "--debug"]),
    ):
        mock_get_logger.return_value = MagicMock()
        mock_init_cfg.return_value = mock_config_manager

        server.main()

        mock_setup.assert_called_once_with("DEBUG")


def test_default_logging_level_is_info(mock_config_manager):
    """Without --debug, structured logging should use INFO."""
    with (
        patch("src.zulipchat_mcp.server.setup_structured_logging") as mock_setup,
        patch("src.zulipchat_mcp.server.get_logger") as mock_get_logger,
        patch("src.zulipchat_mcp.server.init_config_manager") as mock_init_cfg,
        patch.object(sys, "argv", ["zulipchat-mcp"]),
    ):
        mock_get_logger.return_value = MagicMock()
        mock_init_cfg.return_value = mock_config_manager

        server.main()

        mock_setup.assert_called_once_with("INFO")


def test_server_disables_global_fastmcp_tasks():
    """Task support must be opt-in per tool, not a server-wide default."""
    cfg = MagicMock()
    cfg.validate_config.return_value = True
    logger = MagicMock()
    mcp = MagicMock()

    with (
        patch("src.zulipchat_mcp.server.setup_structured_logging"),
        patch("src.zulipchat_mcp.server.get_logger", return_value=logger),
        patch("src.zulipchat_mcp.server.init_config_manager", return_value=cfg),
        patch("src.zulipchat_mcp.server.init_database"),
        patch("src.zulipchat_mcp.server.FastMCP", return_value=mcp) as mock_fastmcp,
        patch("src.zulipchat_mcp.server.register_core_tools") as mock_register_core,
        patch.object(sys, "argv", ["zulipchat-mcp"]),
    ):
        server.main()

    kwargs = mock_fastmcp.call_args.kwargs
    assert kwargs["tasks"] is False
    assert kwargs["lifespan"] is not None
    mock_register_core.assert_called_once_with(mcp)
    mcp.run.assert_called_once_with()


@pytest.mark.asyncio
async def test_server_lifespan_keeps_listener_lazy_when_disabled():
    """Default startup should not initialize the listener until a tool needs it."""
    cfg = MagicMock()
    svc = MagicMock()

    with (
        patch(
            "src.zulipchat_mcp.server.init_service_manager", return_value=svc
        ) as mock_init,
        patch("src.zulipchat_mcp.server.shutdown_service_manager") as mock_shutdown,
    ):
        server_lifespan = server._build_server_lifespan(cfg, enable_listener=False)
        async with server_lifespan(MagicMock()) as context:
            assert context["service_manager"] is svc

    mock_init.assert_called_once_with(cfg, enable_listener=False)
    svc.start.assert_not_called()
    mock_shutdown.assert_called_once_with()


@pytest.mark.asyncio
async def test_server_lifespan_starts_listener_when_enabled():
    """The explicit listener flag should still start services at server boot."""
    cfg = MagicMock()
    svc = MagicMock()

    with (
        patch("src.zulipchat_mcp.server.init_service_manager", return_value=svc),
        patch("src.zulipchat_mcp.server.shutdown_service_manager") as mock_shutdown,
    ):
        server_lifespan = server._build_server_lifespan(cfg, enable_listener=True)
        async with server_lifespan(MagicMock()) as context:
            assert context["service_manager"] is svc

    svc.start.assert_called_once_with()
    mock_shutdown.assert_called_once_with()


def test_version_flag_exits_zero():
    """--version should exit with status code 0."""
    with patch.object(sys, "argv", ["zulipchat-mcp", "--version"]):
        with pytest.raises(SystemExit) as exc:
            server.main()
    assert exc.value.code == 0

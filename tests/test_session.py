"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import asyncio
from unittest.mock import AsyncMock, patch

from designer_plugin.d3sdk.function import d3function
from designer_plugin.d3sdk.session import D3AsyncSession, D3Session
from designer_plugin.models import PluginPayload, PluginResponse, PluginStatus


# Register a module so D3Function._available_d3functions knows about it.
@d3function("lazy_test_module")
def _lazy_test_fn() -> str:
    return "hello world"


def _make_response() -> PluginResponse:
    return PluginResponse(
        status=PluginStatus(code=0, message="OK", details=[]),
        returnValue=None,
    )


def _module_payload() -> PluginPayload:
    """Payload that references a registered @d3function module."""
    return PluginPayload(moduleName="lazy_test_module", script="return _lazy_test_fn()")


def _script_payload() -> PluginPayload:
    """Payload with no module (equivalent to @d3pythonscript)."""
    return PluginPayload(moduleName=None, script="return 42")


class TestD3SessionLazyRegistration:
    """Lazy registration behaviour for the synchronous D3Session."""

    def test_registered_modules_starts_empty(self):
        session = D3Session("localhost", 80)
        assert session.registered_modules == set()

    def test_module_registered_on_first_execute(self):
        session = D3Session("localhost", 80)
        with (
            patch("designer_plugin.d3sdk.session.d3_api_register_module") as mock_reg,
            patch("designer_plugin.d3sdk.session.d3_api_execute", return_value=_make_response()),
        ):
            session.execute(_module_payload())
            mock_reg.assert_called_once()
            assert "lazy_test_module" in session.registered_modules

    def test_module_not_re_registered_on_second_execute(self):
        session = D3Session("localhost", 80)
        with (
            patch("designer_plugin.d3sdk.session.d3_api_register_module") as mock_reg,
            patch("designer_plugin.d3sdk.session.d3_api_execute", return_value=_make_response()),
        ):
            session.execute(_module_payload())
            session.execute(_module_payload())
            mock_reg.assert_called_once()

    def test_no_registration_for_script_payload(self):
        """Payloads without a moduleName must never trigger registration."""
        session = D3Session("localhost", 80)
        with (
            patch("designer_plugin.d3sdk.session.d3_api_register_module") as mock_reg,
            patch("designer_plugin.d3sdk.session.d3_api_execute", return_value=_make_response()),
        ):
            session.execute(_script_payload())
            mock_reg.assert_not_called()

    def test_context_module_not_re_registered_lazily(self):
        """A module pre-registered via context_modules must not be registered again in execute()."""
        with (
            patch("designer_plugin.d3sdk.session.d3_api_register_module") as mock_reg,
            patch("designer_plugin.d3sdk.session.d3_api_execute", return_value=_make_response()),
        ):
            with D3Session("localhost", 80, {"lazy_test_module"}) as session:
                assert "lazy_test_module" in session.registered_modules
                session.execute(_module_payload())
            mock_reg.assert_called_once()  # only from __enter__, not from execute()

    def test_registered_modules_updated_after_execute(self):
        session = D3Session("localhost", 80)
        assert "lazy_test_module" not in session.registered_modules
        with (
            patch("designer_plugin.d3sdk.session.d3_api_register_module"),
            patch("designer_plugin.d3sdk.session.d3_api_execute", return_value=_make_response()),
        ):
            session.execute(_module_payload())
        assert "lazy_test_module" in session.registered_modules


class TestD3AsyncSessionLazyRegistration:
    """Lazy registration behaviour for the asynchronous D3AsyncSession."""

    def test_registered_modules_starts_empty(self):
        session = D3AsyncSession("localhost", 80)
        assert session.registered_modules == set()

    def test_module_registered_on_first_execute(self):
        async def run():
            session = D3AsyncSession("localhost", 80)
            with (
                patch("designer_plugin.d3sdk.session.d3_api_aregister_module", new_callable=AsyncMock) as mock_reg,
                patch("designer_plugin.d3sdk.session.d3_api_aexecute", new_callable=AsyncMock) as mock_exec,
            ):
                mock_exec.return_value = _make_response()
                await session.execute(_module_payload())
                mock_reg.assert_called_once()
                assert "lazy_test_module" in session.registered_modules

        asyncio.run(run())

    def test_module_not_re_registered_on_second_execute(self):
        async def run():
            session = D3AsyncSession("localhost", 80)
            with (
                patch("designer_plugin.d3sdk.session.d3_api_aregister_module", new_callable=AsyncMock) as mock_reg,
                patch("designer_plugin.d3sdk.session.d3_api_aexecute", new_callable=AsyncMock) as mock_exec,
            ):
                mock_exec.return_value = _make_response()
                await session.execute(_module_payload())
                await session.execute(_module_payload())
                mock_reg.assert_called_once()

        asyncio.run(run())

    def test_no_registration_for_script_payload(self):
        """Payloads without a moduleName must never trigger registration."""
        async def run():
            session = D3AsyncSession("localhost", 80)
            with (
                patch("designer_plugin.d3sdk.session.d3_api_aregister_module", new_callable=AsyncMock) as mock_reg,
                patch("designer_plugin.d3sdk.session.d3_api_aexecute", new_callable=AsyncMock) as mock_exec,
            ):
                mock_exec.return_value = _make_response()
                await session.execute(_script_payload())
                mock_reg.assert_not_called()

        asyncio.run(run())

    def test_context_module_not_re_registered_lazily(self):
        """A module pre-registered via context_modules must not be registered again in execute()."""
        async def run():
            with (
                patch("designer_plugin.d3sdk.session.d3_api_aregister_module", new_callable=AsyncMock) as mock_reg,
                patch("designer_plugin.d3sdk.session.d3_api_aexecute", new_callable=AsyncMock) as mock_exec,
            ):
                mock_exec.return_value = _make_response()
                async with D3AsyncSession("localhost", 80, {"lazy_test_module"}) as session:
                    assert "lazy_test_module" in session.registered_modules
                    await session.execute(_module_payload())
                mock_reg.assert_called_once()

        asyncio.run(run())

    def test_registered_modules_updated_after_execute(self):
        async def run():
            session = D3AsyncSession("localhost", 80)
            assert "lazy_test_module" not in session.registered_modules
            with (
                patch("designer_plugin.d3sdk.session.d3_api_aregister_module", new_callable=AsyncMock),
                patch("designer_plugin.d3sdk.session.d3_api_aexecute", new_callable=AsyncMock) as mock_exec,
            ):
                mock_exec.return_value = _make_response()
                await session.execute(_module_payload())
            assert "lazy_test_module" in session.registered_modules

        asyncio.run(run())

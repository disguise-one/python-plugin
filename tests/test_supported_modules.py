from designer_plugin.d3sdk import d3function, D3AsyncSession
from designer_plugin.d3sdk.builtin_modules import SUPPORTED_MODULES, NOT_SUPPORTED_MODULES

import pytest
import asyncio

@d3function('test_supported_modules')
def check_import(module_str) -> bool:
    try:
        module = __import__(module_str)
        return True
    except ImportError as e:
        return False

class TestSupportedModules:
    """
    Test if supported and not supported modules are handled properly on Deisgner side.
    This is integration test so Designer must be running to pass the test.
    """

    @pytest.mark.integration
    def test_supported_modules(self):
        """Test if all supported modules are able to be imported on Designer side."""
        async def run():
            failed = []
            async with D3AsyncSession("localhost", 80) as session:
                for module_str in SUPPORTED_MODULES:
                    import_success: bool = await session.rpc(
                        check_import.payload(module_str)
                    )
                    if not import_success:
                        failed.append(module_str)
            assert not failed, f"Failed to import: {failed}"
        asyncio.run(run())

    @pytest.mark.integration
    def test_not_supported_modules(self):
        """Test if all not supported modules are not importable on Designer side."""
        async def run():
            failed = []
            async with D3AsyncSession("localhost", 80) as session:
                for module_str in NOT_SUPPORTED_MODULES:
                    import_success: bool = await session.rpc(
                        check_import.payload(module_str)
                    )
                    if import_success:
                        failed.append(module_str)
            assert not failed, f"Unexpectedly imported: {failed}"
        asyncio.run(run())

"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd

Tests for D3PluginClient signature validation and method wrapping.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from designer_plugin.d3sdk.client import D3PluginClient
from designer_plugin.models import PluginResponse, PluginStatus


class SignatureValidationPlugin(D3PluginClient):
    """Test plugin class for signature validation tests."""

    def __init__(self, config_value: str):
        super().__init__()
        self.config_value = config_value

    def simple_method(self, a: int, b: int) -> int:
        """Simple method with two required parameters."""
        return a + b

    def method_with_defaults(self, x: int, y: int = 10, z: int = 20) -> int:
        """Method with default parameters."""
        return x + y + z

    def method_positional_only(self, a: int, b: int, /) -> int:
        """Method with positional-only parameters (Python 3.8+)."""
        return a * b

    def method_keyword_only(self, *, name: str, value: int) -> str:
        """Method with keyword-only parameters."""
        return f"{name}={value}"

    def method_mixed(self, a: int, b: int = 5, *, c: str) -> str:
        """Method with mixed parameter types."""
        return f"a={a}, b={b}, c={c}"

    async def async_method(self, x: int, y: int) -> int:
        """Async method for testing async wrapper."""
        return x * y


class TestSignatureValidation:
    """Test suite for signature validation in wrapped methods."""

    @pytest.fixture
    def plugin(self):
        """Create a test plugin instance."""
        return SignatureValidationPlugin("test_config")

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        return PluginResponse(
            status=PluginStatus(code=0, message="Success", details=[]),
            returnValue=42
        )

    def test_method_call_without_session_raises_error(self, plugin):
        """Test that calling a method outside of a session raises RuntimeError."""
        # Verify plugin is not in session
        assert not plugin.in_session()

        # Attempt to call a method without being in a session
        with pytest.raises(RuntimeError, match="is not in.*session"):
            plugin.simple_method(1, 2)

    def test_correct_arguments_sync(self, plugin, mock_response):
        """Test that correct arguments pass through successfully."""
        with patch('designer_plugin.d3sdk.client.d3_api_plugin', return_value=mock_response) as mock_api:
            plugin._hostname = "localhost"
            plugin._port = 80

            result = plugin.simple_method(5, 10)

            assert result == 42
            mock_api.assert_called_once()

    def test_too_many_positional_arguments(self, plugin):
        """Test that too many positional arguments raise TypeError."""
        plugin._hostname = "localhost"
        plugin._port = 80

        with pytest.raises(TypeError, match="too many positional arguments"):
            plugin.simple_method(1, 2, 3)

    def test_multiple_values_for_argument(self, plugin):
        """Test that multiple values for same argument raise TypeError."""
        plugin._hostname = "localhost"
        plugin._port = 80

        with pytest.raises(TypeError, match="multiple values for argument"):
            plugin.simple_method(1, a=2)

    def test_missing_required_argument(self, plugin):
        """Test that missing required arguments raise TypeError."""
        plugin._hostname = "localhost"
        plugin._port = 80

        with pytest.raises(TypeError, match="missing a required argument"):
            plugin.simple_method(1)

    def test_unexpected_keyword_argument(self, plugin):
        """Test that unexpected keyword arguments raise TypeError."""
        plugin._hostname = "localhost"
        plugin._port = 80

        with pytest.raises(TypeError, match="got an unexpected keyword argument"):
            plugin.simple_method(1, 2, unexpected=3)

    def test_method_with_defaults_partial_args(self, plugin, mock_response):
        """Test method with default parameters using partial arguments."""
        with patch('designer_plugin.d3sdk.client.d3_api_plugin', return_value=mock_response):
            plugin._hostname = "localhost"
            plugin._port = 80

            # Should work with just required argument
            result = plugin.method_with_defaults(5)
            assert result == 42

    def test_method_with_defaults_override(self, plugin, mock_response):
        """Test method with default parameters overriding defaults."""
        with patch('designer_plugin.d3sdk.client.d3_api_plugin', return_value=mock_response):
            plugin._hostname = "localhost"
            plugin._port = 80

            # Should work with overriding defaults
            result = plugin.method_with_defaults(5, 15, 25)
            assert result == 42

    def test_method_with_defaults_keyword(self, plugin, mock_response):
        """Test method with default parameters using keyword arguments."""
        with patch('designer_plugin.d3sdk.client.d3_api_plugin', return_value=mock_response):
            plugin._hostname = "localhost"
            plugin._port = 80

            # Should work with keyword arguments
            result = plugin.method_with_defaults(5, z=30)
            assert result == 42

    def test_keyword_only_parameters(self, plugin, mock_response):
        """Test method with keyword-only parameters."""
        with patch('designer_plugin.d3sdk.client.d3_api_plugin', return_value=mock_response):
            plugin._hostname = "localhost"
            plugin._port = 80

            # Should work with keyword arguments
            result = plugin.method_keyword_only(name="test", value=100)
            assert result == 42

    def test_keyword_only_parameters_as_positional_fails(self, plugin):
        """Test that keyword-only parameters cannot be passed as positional."""
        plugin._hostname = "localhost"
        plugin._port = 80

        with pytest.raises(TypeError, match="too many positional arguments"):
            plugin.method_keyword_only("test", 100)

    def test_mixed_parameters(self, plugin, mock_response):
        """Test method with mixed parameter types."""
        with patch('designer_plugin.d3sdk.client.d3_api_plugin', return_value=mock_response):
            plugin._hostname = "localhost"
            plugin._port = 80

            result = plugin.method_mixed(1, 2, c="test")
            assert result == 42

    def test_mixed_parameters_missing_keyword_only(self, plugin):
        """Test that missing keyword-only parameter raises TypeError."""
        plugin._hostname = "localhost"
        plugin._port = 80

        with pytest.raises(TypeError, match="missing a required*"):
            plugin.method_mixed(1, 2)

    def test_async_method_signature_validation(self, plugin):
        """Test that async methods have signature validation (check without running)."""
        import inspect

        # Verify the async_method is wrapped
        assert callable(plugin.async_method)

        # The wrapper should preserve the function metadata
        assert plugin.async_method.__name__ == "async_method"


class TestValidateAndExtractArgs:
    """Test suite for validate_and_extract_args helper function."""

    def test_positional_arguments_extraction(self):
        """Test that positional arguments are correctly extracted."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b, c):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None, 1, 2, 3), {})

        assert positional == (1, 2, 3)
        assert keyword == {}

    def test_keyword_arguments_extraction(self):
        """Test that keyword arguments are correctly extracted."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, *, a, b):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None,), {'a': 1, 'b': 2})

        assert positional == ()
        assert keyword == {'a': 1, 'b': 2}

    def test_mixed_arguments_extraction(self):
        """Test that mixed arguments are correctly extracted."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b=5, *, c):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None, 1), {'b': 10, 'c': 'test'})

        assert positional == (1, 10)
        assert keyword == {'c': 'test'}

    def test_defaults_applied(self):
        """Test that default values are applied correctly."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b=10, c=20):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None, 1), {})

        # Should include defaults
        assert positional == (1, 10, 20)
        assert keyword == {}

    def test_invalid_signature_raises_type_error(self):
        """Test that invalid signatures raise TypeError."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b):
            pass

        sig = inspect.signature(test_func)

        with pytest.raises(TypeError):
            validate_and_extract_args(sig, True, (None, 1, 2, 3), {})


class TestModuleNameOverride:
    """Test suite for module_name override functionality."""

    @pytest.fixture
    def plugin(self):
        """Create a test plugin instance."""
        return SignatureValidationPlugin("test_config")

    def test_override_module_name_in_session(self, plugin):
        """Test that module_name parameter overrides the default in session."""
        with patch('designer_plugin.d3sdk.client.d3_api_register_module') as mock_register:
            # Get the original module_name
            original_module_name = plugin.module_name

            # Use session with a custom module name
            with plugin.session("localhost", 80, register_module=True, module_name="CustomModule"):
                # Verify the register was called with the overridden name
                mock_register.assert_called_once()
                call_args = mock_register.call_args
                payload = call_args[0][2]  # Third positional argument is the payload
                assert payload.moduleName == "CustomModule"
                assert payload.moduleName != original_module_name

            # After session ends, verify the override is cleared
            assert plugin._override_module_name is None
            # Verify the class module_name is unchanged
            assert plugin.module_name == original_module_name

    def test_no_override_uses_default_module_name(self, plugin):
        """Test that without module_name parameter, default module_name is used."""
        with patch('designer_plugin.d3sdk.client.d3_api_register_module') as mock_register:
            original_module_name = plugin.module_name

            # Use session without custom module name
            with plugin.session("localhost", 80, register_module=True):
                mock_register.assert_called_once()
                call_args = mock_register.call_args
                payload = call_args[0][2]
                assert payload.moduleName == original_module_name

            # Verify no override was set
            assert plugin._override_module_name is None

    def test_override_cleared_on_exception(self, plugin):
        """Test that module_name override is cleared even if an exception occurs."""
        with patch('designer_plugin.d3sdk.client.d3_api_register_module', side_effect=Exception("Test error")):
            original_module_name = plugin.module_name

            # Use session with custom module name, expect exception
            with pytest.raises(Exception, match="Test error"):
                with plugin.session("localhost", 80, register_module=True, module_name="CustomModule"):
                    pass

            # Verify the override is cleared despite the exception
            assert plugin._override_module_name is None
            # Verify the class module_name is unchanged
            assert plugin.module_name == original_module_name

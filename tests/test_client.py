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

    def test_var_positional_args_extraction(self):
        """Test that *args are correctly unpacked into positional arguments."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b, *args):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None, 1, 2, 3, 4, 5), {})

        assert positional == (1, 2, 3, 4, 5)
        assert keyword == {}

    def test_var_positional_empty_args(self):
        """Test that empty *args are handled correctly."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b, *args):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None, 1, 2), {})

        assert positional == (1, 2)
        assert keyword == {}

    def test_var_keyword_kwargs_extraction(self):
        """Test that **kwargs are correctly unpacked into keyword arguments."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, **kwargs):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(
            sig, True, (None, 1), {'x': 10, 'y': 20, 'z': 30}
        )

        assert positional == (1,)
        assert keyword == {'x': 10, 'y': 20, 'z': 30}

    def test_var_keyword_empty_kwargs(self):
        """Test that empty **kwargs are handled correctly."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, **kwargs):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None, 1), {})

        assert positional == (1,)
        assert keyword == {}

    def test_mixed_args_and_kwargs(self):
        """Test function with both *args and **kwargs."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b, *args, **kwargs):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(
            sig, True, (None, 1, 2, 3, 4), {'x': 10, 'y': 20}
        )

        assert positional == (1, 2, 3, 4)
        assert keyword == {'x': 10, 'y': 20}

    def test_complex_signature_with_all_parameter_types(self):
        """Test function with all parameter types: positional, *args, keyword-only, **kwargs."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b, *args, c, d=10, **kwargs):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(
            sig, True, (None, 1, 2, 3, 4), {'c': 5, 'd': 15, 'x': 100, 'y': 200}
        )

        # Positional should include a, b, and *args
        assert positional == (1, 2, 3, 4)
        # Keyword should include c, d (keyword-only), and **kwargs
        assert keyword == {'c': 5, 'd': 15, 'x': 100, 'y': 200}

    def test_positional_only_with_var_positional(self):
        """Test function with positional-only parameters and *args."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, b, /, *args):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(sig, True, (None, 1, 2, 3, 4, 5), {})

        assert positional == (1, 2, 3, 4, 5)
        assert keyword == {}

    def test_var_positional_preserves_order(self):
        """Test that *args values maintain their order in the positional list."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, *args):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(
            sig, True, (None, 'a', 'b', 'c', 'd', 'e'), {}
        )

        assert positional == ('a', 'b', 'c', 'd', 'e')
        assert keyword == {}

    def test_var_keyword_with_keyword_only_params(self):
        """Test that **kwargs works correctly with keyword-only parameters."""
        from designer_plugin.d3sdk.ast_utils import validate_and_extract_args
        import inspect

        def test_func(self, a, *, b, c, **kwargs):
            pass

        sig = inspect.signature(test_func)
        positional, keyword = validate_and_extract_args(
            sig, True, (None, 1), {'b': 2, 'c': 3, 'x': 10, 'y': 20}
        )

        assert positional == (1,)
        assert keyword == {'b': 2, 'c': 3, 'x': 10, 'y': 20}


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

    def test_get_module_name_returns_default_when_no_override(self, plugin):
        """Test that _get_module_name returns default module_name when no override is set."""
        # Ensure no override is set
        assert plugin._override_module_name is None

        # Get the original module_name
        original_module_name = plugin.module_name

        # _get_module_name should return the default
        assert plugin._get_module_name() == original_module_name

    def test_get_module_name_returns_override_when_set(self, plugin):
        """Test that _get_module_name returns override when set."""
        original_module_name = plugin.module_name
        override_name = "OverriddenModule"

        # Set an override
        plugin._override_module_name = override_name

        # _get_module_name should return the override
        assert plugin._get_module_name() == override_name
        assert plugin._get_module_name() != original_module_name

        # Clean up
        plugin._override_module_name = None

    def test_get_module_name_during_session_with_override(self, plugin):
        """Test that _get_module_name returns override during session context."""
        with patch('designer_plugin.d3sdk.client.d3_api_register_module'):
            original_module_name = plugin.module_name
            override_name = "SessionModule"

            with plugin.session("localhost", 80, register_module=True, module_name=override_name):
                # During session, _get_module_name should return the override
                assert plugin._get_module_name() == override_name
                assert plugin._get_module_name() != original_module_name

            # After session, should return to default
            assert plugin._get_module_name() == original_module_name

    def test_get_module_name_during_session_without_override(self, plugin):
        """Test that _get_module_name returns default during session without override."""
        with patch('designer_plugin.d3sdk.client.d3_api_register_module'):
            original_module_name = plugin.module_name

            with plugin.session("localhost", 80, register_module=True):
                # Without override, should return default module_name
                assert plugin._get_module_name() == original_module_name

            # After session, should still return default
            assert plugin._get_module_name() == original_module_name


class TestBuildPayload:
    """Test suite for build_payload function."""

    @pytest.fixture
    def plugin(self):
        """Create a test plugin instance."""
        return SignatureValidationPlugin("test_config")

    def test_build_payload_with_no_arguments(self, plugin):
        """Test build_payload with method that takes no arguments."""
        from designer_plugin.d3sdk.client import build_payload

        payload = build_payload(plugin, "simple_method", (), {})

        assert payload.moduleName == plugin.module_name
        assert payload.script == "return plugin.simple_method()"

    def test_build_payload_with_positional_arguments(self, plugin):
        """Test build_payload with positional arguments."""
        from designer_plugin.d3sdk.client import build_payload

        payload = build_payload(plugin, "simple_method", (1, 2), {})

        assert payload.moduleName == plugin.module_name
        assert payload.script == "return plugin.simple_method(1, 2)"

    def test_build_payload_with_keyword_arguments(self, plugin):
        """Test build_payload with keyword arguments."""
        from designer_plugin.d3sdk.client import build_payload

        payload = build_payload(plugin, "method_keyword_only", (), {"name": "test", "value": 100})

        assert payload.moduleName == plugin.module_name
        assert payload.script == "return plugin.method_keyword_only(name='test', value=100)"

    def test_build_payload_with_mixed_arguments(self, plugin):
        """Test build_payload with both positional and keyword arguments."""
        from designer_plugin.d3sdk.client import build_payload

        payload = build_payload(plugin, "method_mixed", (1, 2), {"c": "test"})

        assert payload.moduleName == plugin.module_name
        assert payload.script == "return plugin.method_mixed(1, 2, c='test')"

    def test_build_payload_with_string_arguments(self, plugin):
        """Test build_payload correctly escapes string arguments."""
        from designer_plugin.d3sdk.client import build_payload

        payload = build_payload(plugin, "some_method", ("hello world",), {"key": "value with spaces"})

        assert payload.moduleName == plugin.module_name
        # repr() should properly quote strings
        assert "plugin.some_method('hello world', key='value with spaces')" in payload.script

    def test_build_payload_with_various_types(self, plugin):
        """Test build_payload handles various argument types."""
        from designer_plugin.d3sdk.client import build_payload

        payload = build_payload(plugin, "some_method", (42, 3.14, True, None, [1, 2, 3]), {})

        assert payload.moduleName == plugin.module_name
        assert payload.script == "return plugin.some_method(42, 3.14, True, None, [1, 2, 3])"

    def test_build_payload_uses_override_module_name(self, plugin):
        """Test that build_payload uses override module name when set."""
        from designer_plugin.d3sdk.client import build_payload

        original_module_name = plugin.module_name
        override_name = "OverriddenModule"

        # Set an override
        plugin._override_module_name = override_name

        payload = build_payload(plugin, "simple_method", (), {})

        # Should use the override, not the default
        assert payload.moduleName == override_name
        assert payload.moduleName != original_module_name

        # Clean up
        plugin._override_module_name = None

    def test_build_payload_during_session_with_override(self, plugin):
        """Test build_payload uses override module name during session."""
        from designer_plugin.d3sdk.client import build_payload

        with patch('designer_plugin.d3sdk.client.d3_api_register_module'):
            override_name = "SessionModule"

            with plugin.session("localhost", 80, register_module=True, module_name=override_name):
                payload = build_payload(plugin, "simple_method", (1, 2), {})

                # Should use the session override
                assert payload.moduleName == override_name
                assert payload.script == "return plugin.simple_method(1, 2)"

    def test_build_payload_with_complex_nested_structures(self, plugin):
        """Test build_payload handles nested data structures."""
        from designer_plugin.d3sdk.client import build_payload

        nested_data = {"key": [1, 2, {"inner": "value"}]}
        payload = build_payload(plugin, "some_method", (nested_data,), {})

        assert payload.moduleName == plugin.module_name
        # repr() should handle nested structures
        assert "plugin.some_method(" in payload.script
        assert "'key': [1, 2, {'inner': 'value'}]" in payload.script

    def test_build_payload_method_name_preserved(self, plugin):
        """Test that method names are correctly preserved in the script."""
        from designer_plugin.d3sdk.client import build_payload

        method_names = ["method1", "method_with_underscores", "methodCamelCase"]

        for method_name in method_names:
            payload = build_payload(plugin, method_name, (), {})
            assert f"plugin.{method_name}()" in payload.script


class TestInstanceCodeGenerationWithDefaults:
    """Test suite for instance_code generation with default parameters in __init__.

    This addresses the issue where D3PluginClientMeta.__call__ fails when __init__
    uses defaults or omitted filtered args, causing KeyError during .format().

    The current implementation uses:
        instance_code_template = "plugin = ClassName({arg1},{arg2})"
        instance_code = instance_code_template.format(**arg_mapping)

    This raises KeyError when arg_mapping doesn't contain all placeholders.

    The fix should build the argument string directly from provided args/kwargs:
        arg_strings = [repr(arg) for arg in provided_args]
        instance_code = f"plugin = ClassName({', '.join(arg_strings)})"
    """

    def test_plugin_with_no_defaults_all_args_provided(self):
        """Test plugin with no defaults when all arguments are provided."""
        class NoDefaultsPlugin(D3PluginClient):
            def __init__(self, a: int, b: int):
                super().__init__()
                self.a = a
                self.b = b

            def test_method(self) -> int:
                return self.a + self.b

        # Create instance with all args - should work
        plugin = NoDefaultsPlugin(1, 2)

        # Verify instance_code is generated correctly
        assert hasattr(plugin, 'instance_code')
        assert 'NoDefaultsPlugin' in plugin.instance_code
        assert '1' in plugin.instance_code
        assert '2' in plugin.instance_code

    def test_plugin_with_defaults_all_args_provided(self):
        """Test plugin with defaults when all arguments are explicitly provided."""
        class DefaultsPlugin(D3PluginClient):
            def __init__(self, a: int, b: int = 10, c: int = 20):
                super().__init__()
                self.a = a
                self.b = b
                self.c = c

            def test_method(self) -> int:
                return self.a + self.b + self.c

        # Create instance with all args - should work
        plugin = DefaultsPlugin(1, 2, 3)

        # Verify instance_code is generated correctly with all args
        assert hasattr(plugin, 'instance_code')
        assert 'DefaultsPlugin' in plugin.instance_code
        # Should contain all provided values
        assert '1' in plugin.instance_code
        assert '2' in plugin.instance_code
        assert '3' in plugin.instance_code

    def test_plugin_with_defaults_omitting_optional_args(self):
        """Test plugin with defaults when optional arguments are omitted.

        This is the main issue: when a parameter with a default is omitted,
        the current implementation raises KeyError during format().
        """
        class DefaultsPlugin(D3PluginClient):
            def __init__(self, a: int, b: int = 10):
                super().__init__()
                self.a = a
                self.b = b

            def test_method(self) -> int:
                return self.a + self.b

        # Create instance with only required arg - should work with the fix
        plugin = DefaultsPlugin(5)

        # Verify instance_code is generated correctly
        assert hasattr(plugin, 'instance_code')
        assert 'DefaultsPlugin' in plugin.instance_code
        # Should only contain the provided argument
        assert '5' in plugin.instance_code
        # The instance_code should be valid Python that relies on the default
        # With the fix, it should be something like: plugin = DefaultsPlugin(5)
        # NOT: plugin = DefaultsPlugin({a}) which would fail .format()

    def test_plugin_with_multiple_defaults_partial_override(self):
        """Test plugin with multiple defaults, overriding only some."""
        class MultiDefaultsPlugin(D3PluginClient):
            def __init__(self, a: int, b: int = 10, c: int = 20, d: int = 30):
                super().__init__()
                self.a = a
                self.b = b
                self.c = c
                self.d = d

            def test_method(self) -> int:
                return self.a + self.b + self.c + self.d

        # Create instance with required + some optional args
        plugin = MultiDefaultsPlugin(1, 15)

        # Verify instance_code is generated correctly
        assert hasattr(plugin, 'instance_code')
        assert 'MultiDefaultsPlugin' in plugin.instance_code
        assert '1' in plugin.instance_code
        assert '15' in plugin.instance_code
        # c and d should rely on defaults and not appear in instance_code

    def test_plugin_with_defaults_using_keyword_args(self):
        """Test plugin with defaults using keyword arguments."""
        class DefaultsPlugin(D3PluginClient):
            def __init__(self, a: int, b: int = 10, c: int = 20):
                super().__init__()
                self.a = a
                self.b = b
                self.c = c

            def test_method(self) -> int:
                return self.a + self.b + self.c

        # Create instance with keyword args, skipping middle default
        plugin = DefaultsPlugin(1, c=30)

        # Verify instance_code is generated correctly
        assert hasattr(plugin, 'instance_code')
        assert 'DefaultsPlugin' in plugin.instance_code
        assert '1' in plugin.instance_code
        # Should include c as keyword arg
        assert 'c=30' in plugin.instance_code or '30' in plugin.instance_code

    def test_plugin_with_all_defaults_using_positional(self):
        """Test plugin where all parameters have defaults, using positional args."""
        class AllDefaultsPlugin(D3PluginClient):
            def __init__(self, a: int = 1, b: int = 2, c: int = 3):
                super().__init__()
                self.a = a
                self.b = b
                self.c = c

            def test_method(self) -> int:
                return self.a + self.b + self.c

        # Create instance with no args - all defaults
        plugin = AllDefaultsPlugin()

        # Verify instance_code is generated correctly (should be empty args)
        assert hasattr(plugin, 'instance_code')
        assert 'AllDefaultsPlugin()' in plugin.instance_code

    def test_plugin_with_all_defaults_partial_override(self):
        """Test plugin where all parameters have defaults, overriding some."""
        class AllDefaultsPlugin(D3PluginClient):
            def __init__(self, a: int = 1, b: int = 2, c: int = 3):
                super().__init__()
                self.a = a
                self.b = b
                self.c = c

            def test_method(self) -> int:
                return self.a + self.b + self.c

        # Create instance with one arg
        plugin = AllDefaultsPlugin(10)

        # Verify instance_code is generated correctly
        assert hasattr(plugin, 'instance_code')
        assert 'AllDefaultsPlugin' in plugin.instance_code
        assert '10' in plugin.instance_code

    def test_plugin_defaults_with_different_types(self):
        """Test plugin with defaults of different types."""
        class TypedDefaultsPlugin(D3PluginClient):
            def __init__(self, name: str, count: int = 5, active: bool = True):
                super().__init__()
                self.name = name
                self.count = count
                self.active = active

            def test_method(self) -> str:
                return f"{self.name}: {self.count}"

        # Create instance with only required arg
        plugin = TypedDefaultsPlugin("test")

        # Verify instance_code is generated correctly
        assert hasattr(plugin, 'instance_code')
        assert 'TypedDefaultsPlugin' in plugin.instance_code
        assert "'test'" in plugin.instance_code

    def test_instance_code_execution_semantics(self):
        """Test that generated instance_code has correct execution semantics.

        The generated code should let the remote side apply defaults,
        not try to substitute them client-side.
        """
        class SemanticsPlugin(D3PluginClient):
            def __init__(self, x: int, y: int = 100):
                super().__init__()
                self.x = x
                self.y = y

            def test_method(self) -> int:
                return self.x + self.y

        # Test case 1: Only required arg
        plugin1 = SemanticsPlugin(5)
        # The instance_code should be: plugin = SemanticsPlugin(5)
        # NOT: plugin = SemanticsPlugin(5, 100) - that would hardcode the default
        assert 'SemanticsPlugin(5)' in plugin1.instance_code
        assert '100' not in plugin1.instance_code  # Default should not appear

        # Test case 2: Override the default
        plugin2 = SemanticsPlugin(5, 200)
        # The instance_code should include the override
        assert 'SemanticsPlugin' in plugin2.instance_code
        assert '5' in plugin2.instance_code
        assert '200' in plugin2.instance_code

    def test_complex_defaults_scenario(self):
        """Test complex scenario with mixed required and optional args."""
        class ComplexPlugin(D3PluginClient):
            def __init__(
                self,
                required1: str,
                required2: int,
                optional1: str = "default1",
                optional2: int = 42,
                optional3: bool = False
            ):
                super().__init__()
                self.required1 = required1
                self.required2 = required2
                self.optional1 = optional1
                self.optional2 = optional2
                self.optional3 = optional3

            def test_method(self) -> str:
                return f"{self.required1}_{self.required2}"

        # Test various combinations

        # All required only
        plugin1 = ComplexPlugin("test", 10)
        assert 'ComplexPlugin' in plugin1.instance_code
        assert "'test'" in plugin1.instance_code
        assert '10' in plugin1.instance_code

        # Required + some optional (positional)
        plugin2 = ComplexPlugin("test", 10, "custom")
        assert 'ComplexPlugin' in plugin2.instance_code
        assert "'test'" in plugin2.instance_code
        assert '10' in plugin2.instance_code
        assert "'custom'" in plugin2.instance_code

        # Required + some optional (keyword)
        plugin3 = ComplexPlugin("test", 10, optional2=99)
        assert 'ComplexPlugin' in plugin3.instance_code
        assert "'test'" in plugin3.instance_code
        assert '10' in plugin3.instance_code
        # Should include the keyword argument
        assert '99' in plugin3.instance_code


class TestInitWrapperSuperCall:
    """Test suite for automatic parent __init__ calling when user forgets super().__init__()."""

    def test_plugin_without_super_init_has_required_attributes(self):
        """Test that plugin works even without calling super().__init__()."""
        class PluginWithoutSuper(D3PluginClient):
            def __init__(self):
                # Deliberately NOT calling super().__init__()
                self.custom_attr = "test"

            def test_method(self) -> str:
                return self.custom_attr

        plugin = PluginWithoutSuper()

        # These attributes should exist even without super().__init__()
        assert hasattr(plugin, '_hostname')
        assert hasattr(plugin, '_port')
        assert hasattr(plugin, '_override_module_name')
        assert hasattr(plugin, 'custom_attr')

        # Verify attribute values are properly initialized
        assert plugin._hostname is None
        assert plugin._port is None
        assert plugin._override_module_name is None
        assert plugin.custom_attr == "test"

    def test_in_session_works_without_super_init(self):
        """Test that in_session() method works without super().__init__()."""
        class PluginWithoutSuper(D3PluginClient):
            def __init__(self):
                self.a = "hey"

            def fn(self, a: int) -> int:
                return a

        plugin = PluginWithoutSuper()

        # in_session() should not raise AttributeError
        assert plugin.in_session() is False

        # After setting hostname and port
        plugin._hostname = "localhost"
        plugin._port = 80
        assert plugin.in_session() is True

    def test_plugin_with_super_init_still_works(self):
        """Test that plugin still works when properly calling super().__init__()."""
        class PluginWithSuper(D3PluginClient):
            def __init__(self):
                super().__init__()
                self.custom_attr = "test"

            def test_method(self) -> str:
                return self.custom_attr

        plugin = PluginWithSuper()

        # All attributes should be present
        assert hasattr(plugin, '_hostname')
        assert hasattr(plugin, '_port')
        assert hasattr(plugin, '_override_module_name')
        assert hasattr(plugin, 'custom_attr')

        # Verify attribute values
        assert plugin._hostname is None
        assert plugin._port is None
        assert plugin._override_module_name is None
        assert plugin.custom_attr == "test"

    def test_no_double_initialization_with_super_call(self):
        """Test that calling super().__init__() doesn't cause double initialization."""
        initialization_count = []

        class PluginWithSuper(D3PluginClient):
            def __init__(self):
                super().__init__()
                initialization_count.append(1)

            def test_method(self) -> str:
                return "test"

        plugin = PluginWithSuper()

        # Should have been initialized exactly once (by the user's __init__)
        assert len(initialization_count) == 1

        # Attributes should still be properly set
        assert plugin._hostname is None
        assert plugin._port is None
        assert plugin._override_module_name is None

    def test_plugin_with_args_without_super_init(self):
        """Test plugin with constructor arguments but no super().__init__() call."""
        class PluginWithArgs(D3PluginClient):
            def __init__(self, value: int, name: str):
                # Not calling super().__init__()
                self.value = value
                self.name = name

            def test_method(self) -> str:
                return f"{self.name}={self.value}"

        plugin = PluginWithArgs(42, "test")

        # Required attributes should exist
        assert hasattr(plugin, '_hostname')
        assert hasattr(plugin, '_port')
        assert hasattr(plugin, '_override_module_name')

        # Custom attributes should be set
        assert plugin.value == 42
        assert plugin.name == "test"

        # in_session() should work
        assert plugin.in_session() is False

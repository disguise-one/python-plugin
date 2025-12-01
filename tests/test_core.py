"""
MIT License
Copyright (c) 2025 Disguise Technologies ltd
"""

import pytest

from designer_plugin.d3sdk.function import (
    D3Function,
    D3PythonScript,
    FunctionInfo,
    d3function,
    d3pythonscript,
    extract_function_info,
    get_all_d3functions,
    get_all_modules,
    get_register_payload,
)


def example_function():
    """Example function for testing"""
    return "hello world"


def example_function_with_args(name, value):
    """Example function with arguments for testing"""
    return f"Hello {name}, value is {value}"


def typed_function_with_args(name: str, value: int) -> str:
    """Type-annotated function with arguments for testing"""
    result: str = f"Hello {name}, value is {value}"
    return result


def typed_function_complex(items: list[str], count: int = 5) -> dict[str, int]:
    """Complex type-annotated function for testing"""
    data: dict[str, int] = {}
    for i, item in enumerate(items[:count]):
        data[item] = i
    return data


@d3function("test_module")
def decorated_example_function():
    """Decorated example function for testing"""
    return "decorated hello world"


@d3function()  # No module name
def standalone_function(x, y):
    """Standalone function for testing"""
    return x + y


@d3function("module_a")
def function_in_module_a():
    """Function in module A for testing"""
    return "module_a_result"


@d3function("module_b")
def function_in_module_b(value):
    """Function in module B for testing"""
    return f"module_b_{value}"


class TestExtractFunctionInfo:
    def test_extract_info_simple_function(self):
        info = extract_function_info(example_function)

        assert info.name == "example_function"
        assert "return 'hello world'" in info.body
        assert info.args == []
        assert "def example_function():" in info.source_code

    def test_extract_info_function_with_args(self):
        info = extract_function_info(example_function_with_args)

        assert info.name == "example_function_with_args"
        assert "return f'Hello {name}, value is {value}'" in info.body
        assert info.args == ["name", "value"]
        assert "def example_function_with_args(name, value):" in info.source_code

    def test_extract_info_decorated_function(self):
        # Test that decorators are removed from the blob
        info = extract_function_info(decorated_example_function._function)

        assert info.name == "decorated_example_function"
        assert "return 'decorated hello world'" in info.body
        assert info.args == []
        # Should not contain the decorator in the blob
        assert "@d3function" not in info.source_code

    def test_extract_info_typed_function(self):
        # Test type annotation handling
        info = extract_function_info(typed_function_with_args)

        assert info.name == "typed_function_with_args"
        assert info.args == ["name", "value"]

        # Regular blob should contain type annotations
        assert ": str" in info.source_code
        assert "-> str" in info.source_code
        assert "result: str" in info.source_code

        # Python 2.7 blob should NOT contain type annotations
        assert ": str" not in info.source_code_py27
        assert "-> str" not in info.source_code_py27
        assert "result: str" not in info.source_code_py27
        # But should contain the variable assignment without type hint
        assert "result =" in info.source_code_py27

    def test_extract_info_complex_typed_function(self):
        # Test complex type annotations
        info = extract_function_info(typed_function_complex)

        assert info.name == "typed_function_complex"
        assert info.args == ["items", "count"]

        # Regular blob should contain complex type annotations
        assert "list[str]" in info.source_code
        assert "dict[str, int]" in info.source_code
        assert "-> dict[str, int]" in info.source_code
        assert "data: dict[str, int]" in info.source_code

        # Python 2.7 blob should NOT contain type annotations
        assert "list[str]" not in info.source_code_py27
        assert "dict[str, int]" not in info.source_code_py27
        assert "-> dict[str, int]" not in info.source_code_py27
        assert "data: dict[str, int]" not in info.source_code_py27
        # But should contain the variable assignment without type hint
        assert "data =" in info.source_code_py27


class TestD3Function:
    def test_d3_function_creation(self):
        d3_func = D3Function("test_module", example_function)

        assert d3_func.name == "example_function"
        assert d3_func.module_name == "test_module"

    def test_d3_function_standalone(self):
        d3_func = D3Function("", standalone_function._function)

        assert d3_func.name == "standalone_function"
        assert d3_func.module_name == ""

    def test_d3_function_call(self):
        # Test that the wrapped function can still be called
        result = decorated_example_function()
        assert result == "decorated hello world"

        result = standalone_function(5, 3)
        assert result == 8

    def test_get_execute_blob_module_function(self):
        payload = decorated_example_function.payload()

        assert payload.moduleName == "test_module"
        assert payload.script == "return decorated_example_function()"

    def test_get_execute_blob_standalone_function(self):
        # standalone_function is still a D3Function (module function with empty module name)
        # so it generates module-style execution scripts
        payload = standalone_function.payload(10, 20)

        assert payload.moduleName == ""
        assert "return standalone_function(10, 20)" in payload.script

    def test_get_module_register_blob(self):
        payload = get_register_payload("test_module")

        assert payload is not None
        assert payload.moduleName == "test_module"
        assert "def decorated_example_function():" in payload.contents



class TestFunctionInfo:
    def test_function_info_creation(self):
        info = FunctionInfo(
            source_code="def test_func(x: int, y: int) -> int:\n    return 42",
            source_code_py27="def test_func(x, y):\n    return 42",
            name="test_func",
            body="return 42",
            body_py27="return 42",
            args=["x", "y"],
        )

        assert info.name == "test_func"
        assert info.body == "return 42"
        assert info.body_py27 == "return 42"
        assert info.args == ["x", "y"]
        assert info.source_code == "def test_func(x: int, y: int) -> int:\n    return 42"
        assert info.source_code_py27 == "def test_func(x, y):\n    return 42"

    def test_function_info_defaults(self):
        info = FunctionInfo(
            source_code="def test_func() -> int:\n    return 42",
            source_code_py27="def test_func():\n    return 42",
            name="test_func",
            body="return 42",
            body_py27="return 42",
        )
        assert info.args == []


class TestD3FunctionDecorator:
    def test_decorator_with_module(self):
        @d3function("my_module")
        def test_func():
            return "test result"

        assert isinstance(test_func, D3Function)
        assert test_func.module_name == "my_module"
        assert test_func.name == "test_func"

    def test_decorator_without_module(self):
        @d3function()
        def test_func():
            return "test result"

        assert isinstance(test_func, D3Function)
        assert test_func.module_name == ""
        assert test_func.name == "test_func"


class TestRegistrationFunctions:
    def test_get_all_modules(self):
        modules = get_all_modules()
        assert "test_module" in modules

    def test_get_all_d3functions(self):
        functions = get_all_d3functions()
        function_names = [name for _, name in functions]
        assert "decorated_example_function" in function_names
        assert "standalone_function" in function_names


class TestD3FunctionEquality:
    def test_hash_and_equality(self):
        func1 = D3Function("module1", example_function)
        func2 = D3Function("module2", example_function)  # Different module, same function

        # Should be equal and have same hash because they wrap the same function
        assert func1 == func2
        assert hash(func1) == hash(func2)

    def test_inequality_different_functions(self):
        func1 = D3Function("module1", example_function)
        func2 = D3Function("module1", example_function_with_args)

        # Should not be equal because they wrap different functions
        assert func1 != func2



class TestD3PythonScript:
    def test_d3pythonscript_decorator(self):
        @d3pythonscript
        def test_func(a: int, b: int) -> int:
            return a + b

        assert isinstance(test_func, D3PythonScript)
        assert test_func.name == "test_func"
        # Verify it can be called
        assert test_func(3, 4) == 7

    def test_d3pythonscript_payload(self):
        @d3pythonscript
        def test_func(a: int, b: int) -> int:
            return a + b

        payload = test_func.payload(5, 3)

        # Script should contain variable assignments and function body
        assert "a=5" in payload.script
        assert "b=3" in payload.script
        assert "return a + b" in payload.script
        # Should not have moduleName for standalone scripts
        assert not hasattr(payload, "moduleName") or payload.moduleName is None

    def test_d3pythonscript_with_kwargs(self):
        @d3pythonscript
        def test_func(a: int, b: int = 10) -> int:
            return a + b

        payload = test_func.payload(5, b=15)

        assert "a=5" in payload.script
        assert "b=15" in payload.script
        assert "return a + b" in payload.script

    def test_d3pythonscript_args_to_assign_with_extra_args(self):
        """Test that _args_to_assign handles extra arguments gracefully.

        This test will fail with the enumerate/indexing implementation:
            args_parts = [f"{self._function_info.args[i]}={repr(arg)}" for i, arg in enumerate(args)]

        But will pass with the zip implementation:
            args_parts = [f"{param}={repr(arg)}" for param, arg in zip(self._function_info.args, args)]

        The enumerate version causes IndexError when len(args) > len(function parameters).
        The zip version stops at the shorter sequence length.
        """
        @d3pythonscript
        def test_func(a: int, b: int) -> int:
            return a + b

        # This function has 2 parameters but we're passing 3 arguments
        # The first implementation will crash with IndexError
        # The second implementation will silently ignore the extra argument
        result = test_func._args_to_assign(1, 2, 3)

        # Should only contain assignments for the defined parameters
        assert "a=1" in result
        assert "b=2" in result
        # The extra argument should be silently ignored by the zip implementation
        assert result.count("=") == 2  # Only 2 assignments

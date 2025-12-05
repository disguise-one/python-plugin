# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-12-02

### Added
- **Client API**: Metaclass-based remote method execution with `D3PluginClient`
  - Support for both sync and async methods
  - Automatic Python 2.7 code conversion for Designer compatibility
  - Session management with context managers
- **Functional API**: Decorator-based remote execution
  - `@d3pythonscript` decorator for one-off script execution
  - `@d3function(module_name)` decorator for reusable module-based functions
  - Function chaining support within modules
- **Session Management**: `D3Session` and `D3AsyncSession` classes
  - `rpc()` method for simple return value retrieval
  - `execute()` method for full response with logs and status
  - Automatic module registration via context managers
- **Type Safety**: Full Pydantic models for all API interactions
  - `PluginPayload`, `PluginResponse`, `RegisterPayload`
  - Generic type support for type-safe return values
- **Logging**: Configurable logging with `enable_debug_logging()`
  - NullHandler by default (library best practice)
  - Granular module-level control
- **AST Utilities**: Python 3 to Python 2.7 code transformation
  - F-string to `.format()` conversion
  - Type annotation removal
  - Async/await removal
  - Automatic package import detection
- Comprehensive test suite with 99 tests covering all major functionality
- CI/CD with GitHub Actions (ruff, mypy, pytest)
- PEP 561 type hints marker (`py.typed`)

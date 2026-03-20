# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-01-06

### Added
- **Lazy module registration**: `D3Session.execute()` and `D3AsyncSession.execute()` now automatically register a `@d3function` module on first use, eliminating the need to declare all modules in `context_modules` upfront.
- `registered_modules` tracking on session instances prevents duplicate registration calls.
- **Jupyter notebook support**: `@d3function` now automatically replaces a previously registered function when the same name is re-registered in the same module, with a warning log. This enables iterative workflows in Jupyter notebooks where cells are re-executed.

### Changed
- `d3_api_plugin` has been renamed to `d3_api_execute`.
- `d3_api_aplugin` has been renamed to `d3_api_aexecute`.
- `context_modules` parameter type updated from `list[str]` to `set[str]` on `D3Session`, `D3AsyncSession`, and `D3SessionBase`.
- Updated documentation to reflect `pystub` proxy support.
- Bumped `actions/checkout` to v6 and `astral-sh/setup-uv` to v7 in CI.
- Added Test PyPI publish workflow (`test-publish.yml`) for dev version releases.

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

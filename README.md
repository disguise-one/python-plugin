# designer-plugin

A Python library for creating and managing plugins for Disguise Designer. This library provides:
- DNS-SD service publishing for plugin discovery
- Remote Python execution on Designer instances
- Multiple execution patterns (Client SDK, Function SDK)

## Installation

To install the plugin, use pip:

```bash
pip install git+https://github.com/disguise-one/python-plugin
```

<br/>

# Publish Plugin

The `DesignerPlugin` class allows you to publish a plugin for the Disguise Designer application. The `port` parameter corresponds to an HTTP server that serves the plugin's web user interface. Below is an example of how to use it (without a server, for clarity).


In the working directory for the plugin (usually next to the plugin script) a `d3plugin.json` should be created. See [The developer documentation](https://developer.disguise.one/plugins/) for more information
```json
{
    "name": "MyPlugin",
    "requiresSession": true
}
```

The script may work with `asyncio` or be synchronous - both options are shown in this example:
```python
from designer_plugin import DesignerPlugin

# Synchronous usage
from time import sleep
with DesignerPlugin.default_init(12345) as plugin:
    print("Plugin is published. Press Ctrl+C to stop.")
    try:
        while True:
            sleep(3600)
    except KeyboardInterrupt:
        pass

# Asynchronous usage
import asyncio

async def main():
    async with DesignerPlugin.default_init(port=12345) as plugin:
        print("Plugin is published. Press Ctrl+C to stop.")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass

asyncio.run(main())
```

### Publish options

If you would prefer not to use the `d3plugin.json` file, construct the `DesignerPlugin` object directly. The plugin's name and port number are required parameters. Optionally, the plugin can specify `hostname`, which can be used to direct Designer to a specific hostname when opening the plugin's web UI, and other metadata parameters are available, also.

<br/>

# Execute Python

Python scripts can be executed remotely on Designer via the plugin system.

Direct interaction with the plugin API endpoint requires extensive boilerplate code and JSON parsing. However, the Client SDK and Function SDK simplify this process by providing an RPC (Remote Procedure Call) interface that abstracts away the underlying HTTP communication and payload management.

> **Important:** The Designer plugin API only supports Python 2.7, not Python 3. Both the Client SDK and Function SDK attempt to automatically convert your Python 3 code to Python 2.7 (f-strings and type hints are supported). However, some Python 3 features may not be fully compatible and conversion may fail in certain cases. 

## Client SDK

The Client SDK allows you to define a class with methods that execute remotely on Designer by simply inheriting from `D3PluginClient`. The Client SDK supports both async and sync methods.

**Example**

```python
from designer_plugin.d3sdk import D3PluginClient
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from designer_plugin.d3sdk.script.d3 import *

# 1. Async example ----------------------------------
# Define your class by inheriting from D3PluginClient
class MyAsyncPlugin(D3PluginClient):

    async def my_time(self) -> str:
        # Builtin imports must be done within methods for remote execution
        import datetime
        return str(datetime.datetime.now())

    async def get_surface_uid_with_time(
        self,
        surface_name: str
    ) -> dict[str, str]:
        surface: Screen2 = resourceManager.load(
            Path('objects/screen2/{}.apx'.format(surface_name)),
            Screen2)
        return {
            "name": surface.description,
            "uid": str(surface.uid),
            "time": await self.my_time()  # Supports method chaining
        }

# Instantiate your plugin
my_async_plugin = MyAsyncPlugin()
# Start async session with Designer instance
async with my_async_plugin.async_session('localhost', 80):
    # Methods execute remotely on Designer and return values
    surface_info = await my_async_plugin.get_surface_uid_with_time("surface 1")


# 2. Sync example -----------------------------------
class MySyncPlugin(D3PluginClient):
    def get_uid(self, surface_name: str) -> str:
        surface: Screen2 = resourceManager.load(
            Path('objects/screen2/{}.apx'.format(surface_name)),
            Screen2)
        return str(surface.uid)

my_sync_plugin = MySyncPlugin()
with my_sync_plugin.session('localhost', 80):
    uid = my_sync_plugin.get_uid("surface 1")
```

## Function SDK

The Function SDK provides finer control over remote execution compared to the Client SDK. While the Client SDK automatically manages the entire execution lifecycle (registration and execution are transparent), the Function SDK gives you explicit control over:

- **Payload generation**: Decorators add a `payload()` method to generate execution payloads
- **Session management**: You manually create sessions and control when to register modules
- **Function grouping**: Group related functions into modules for efficient reuse
- **Response handling**: Choose between `session.plugin()` for full response (status, logs, return value) or `session.rpc()` for just the return value

The Function SDK offers two decorators: `@d3pythonscript` and `@d3function`:
- **`@d3pythonscript`**: 
  - Does not require registration.
  - Best for simple scripts executed once or infrequently.
- **`@d3function`**:
  - Must be registered on Designer before execution.
  - Functions decorated with the same `module_name` are grouped together and can call each other, enabling function chaining and code reuse.
  - Both `D3AsyncSession` and `D3Session` handle registration when you specify module names in the context manager.

### Session API Methods

Both `D3AsyncSession` and `D3Session` provide two methods for executing functions:

- **`session.rpc(payload)`** - Returns only the return value from the function execution. Simpler for most use cases.
- **`session.plugin(payload)`** - Returns a `PluginResponse` object containing:
  - `returnValue`: The function's return value
  - `status`: Execution status (code, message, details)
  - `d3Log`: Designer console output during execution
  - `pythonLog`: Python-specific output (print statements, warnings)

**Example**

```python
from designer_plugin.d3sdk import d3pythonscript, d3function, D3AsyncSession
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from designer_plugin.d3sdk.script.d3 import *

# 1. @d3pythonscript - simple one-off execution
@d3pythonscript
def rename_surface(surface_name: str, new_name: str):
    surface: Screen2 = resourceManager.load(
        Path('objects/screen2/{}.apx'.format(surface_name)),
        Screen2)
    surface.rename(surface.path.replaceFilename(new_name))

# 2. @d3function - reusable module-based functions
@d3function("mymodule")
def rename_surface_get_time(surface_name: str, new_name: str) -> str:
    surface: Screen2 = resourceManager.load(
        Path('objects/screen2/{}.apx'.format(surface_name)),
        Screen2)
    surface.rename(surface.path.replaceFilename(new_name))
    return my_time()  # Call other functions in the same module

@d3function("mymodule")
def my_time() -> str:
    import datetime
    return str(datetime.datetime.now())

# Usage with async session
async with D3AsyncSession('localhost', 80, ["mymodule"]) as session:
    # d3pythonscript: no registration needed
    await session.rpc(rename_surface.payload("surface 1", "surface 2"))

    # d3function: registered automatically via context manager
    time: str = await session.rpc(
        rename_surface_get_time.payload("surface 1", "surface 2"))

    # Use plugin() for full response with logs and status
    from designer_plugin.d3sdk import PluginResponse
    response: PluginResponse = await session.plugin(
        rename_surface_get_time.payload("surface 1", "surface 2"))
    print(f"Status: {response.status.code}")
    print(f"Return value: {response.returnValue}")

# Sync usage
from designer_plugin.d3sdk import D3Session
with D3Session('localhost', 80, ["mymodule"]) as session:
    session.rpc(rename_surface.payload("surface 1", "surface 2"))
```

<br/>

# Logging

By default, `designer_plugin` logging is disabled. To enable it:

```python
# Quick debug mode
from designer_plugin.logger import enable_debug_logging
enable_debug_logging()

# Or configure via standard logging
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('designer_plugin').setLevel(logging.DEBUG)
```

For production, use your application's logging configuration instead of `enable_debug_logging()`.

<br/>

# License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


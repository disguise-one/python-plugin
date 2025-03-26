# python-plugin

A small Python library which publishes the DNS-SD service for a plugin.

## Installation

To install the plugin, use pip:

```bash
pip install git+https://github.com/disguise-one/python-plugin
```

## Usage

The `DesignerPlugin` class allows you to publish a plugin for the Disguise Designer application. The `port` parameter corresponds to an HTTP server that serves the plugin's web user interface. Below is an example of how to use it (without a server).

```python
from designer_plugin import DesignerPlugin

# Synchronous usage
from time import sleep
with DesignerPlugin(name="MyPlugin", port=12345) as plugin:
    print("Plugin is published. Press Ctrl+C to stop.")
    try:
        while True:
            sleep(3600)
    except KeyboardInterrupt:
        pass

# Asynchronous usage
import asyncio

async def main():
    async with DesignerPlugin(name="MyPlugin", port=12345) as plugin:
        print("Plugin is published. Press Ctrl+C to stop.")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass

asyncio.run(main())
```

## Plugin options

The plugin's name and port number are require parameters. Optionally, the plugin can specify `hostname`, which can be used to direct Designer to a specific hostname when opening the plugin's web UI.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


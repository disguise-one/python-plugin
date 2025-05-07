# python-plugin

A small Python library which publishes the DNS-SD service for a plugin.

## Installation

To install the plugin, use pip:

```bash
pip install git+https://github.com/disguise-one/python-plugin
```

## Usage

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

## Plugin options

If you would prefer not to use the `d3plugin.json` file, construct the `DesignerPlugin` object directly. The plugin's name and port number are required parameters. Optionally, the plugin can specify `hostname`, which can be used to direct Designer to a specific hostname when opening the plugin's web UI, and other metadata parameters are available, also.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


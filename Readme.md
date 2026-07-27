# Eta Right Click

## Overview

Eta Right Click is a utility designed to emulate right-click actions through long press gestures on touch devices. This tool is particularly useful for enhancing user interaction in environments where traditional right-click functionality is not available or convenient.

## Features

- **Long Press Right Click**: A long press on the touch device will trigger a right-click action.
- **Contextual Right Click**: When selecting items with a long press, the right-click action will apply to the selected items.

## Usage

- **Long Press**: Simply press and hold on the touch device. After a brief moment, a right-click action will be executed.

## Configuration

The script can be configured by editing the `/etc/pardus/eta-right-click.conf` file. The following parameters can be adjusted:

- `timeout`: Sets the duration to wait for a long press before triggering a right-click (default: 500 ms).
- `threshold`: Defines the minimum movement pixel to ignore touch events (default: 20).

### Example Configuration File

```ini
[main]
timeout=500
threshold=20

[event]
hold=right-click
release=ignore
tap=ignore
```

## Running the Script

To run the script, execute the following command with root in the terminal:

```bash
python3 src/main.py
```

You can enable debug mode by adding `--debug` to the command line for additional logging:

```bash
python3 src/main.py --debug
```

## Troubleshooting

- **Permission Issues**: Ensure you have the necessary permissions to access input devices. Running the script with root must be required.
- **Device Not Detected**: Check if the input device is connected and recognized by the system. Use `ls /dev/input` to list available devices.
- **Configuration Errors**: Ensure the configuration file is correctly formatted and accessible.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

## Acknowledgments

- The `evdev` library for handling input events.
- The `GLib` library for managing the event loop.

# Eta Right Click

## Overview

Eta Right Click is a utility designed to emulate right-click actions through long press gestures on touch devices. This tool is particularly useful for enhancing user interaction in environments where traditional right-click functionality is not available or convenient.

## Features

- **Long Press Right Click**: A long press on the touch device will trigger a right-click action.
- **Contextual Right Click**: When selecting items with a long press, the right-click action will apply to the selected items.

## Usage

- **Long Press**: Simply press and hold on the touch device. After a brief moment, a right-click action will be executed.
- **Long Press and Select**: While holding down, move your finger to select items. Releasing will trigger a right-click on the selected items.

## Configuration

The script can be configured by editing the `/etc/pardus/eta-right-click.conf` file. The following parameters can be adjusted:

- `sensitive`: Adjusts the sensitivity for touch detection (default: 0.1).
- `timeout`: Sets the duration to wait for a long press before triggering a right-click (default: 700 ms).
- `threshold`: Defines the minimum movement ratio to ignore touch events (default: 0.05).

### Example Configuration File

```ini
[main]
sensitive = 0.1
timeout = 700
threshold = 0.05
```

## Running the Script

To run the script, execute the following command in the terminal:

```bash
sudo python3 eta_right_click.py
```

You can enable debug mode by adding `--debug` to the command line for additional logging:

```bash
sudo python3 eta_right_click.py --debug
```

## Troubleshooting

- **Permission Issues**: Ensure you have the necessary permissions to access input devices. Running the script with `sudo` may be required.
- **Device Not Detected**: Check if the input device is connected and recognized by the system. Use `ls /dev/input` to list available devices.
- **Configuration Errors**: Ensure the configuration file is correctly formatted and accessible.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

## Acknowledgments

- The `evdev` library for handling input events.
- The `GLib` library for managing the event loop.

Feel free to modify and adapt the script as needed for your specific use case!
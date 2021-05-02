# i3status-wrapper

Simple wrapper using `i3status` to generate `i3bar` input.

## Motivation

`i3status` provides reasonable default implementations of various blocks for status line, but provides no (useful) functionality of adding clickable elements.

## Installation

1. Download `i3status-wrapper`, make it executable (`chmod +x i3status-wrapper`) and copy it to `~/.local/bin/` (`cp i3status-wrapper ~/.local/bin/`).
2. Set output format of `i3status` to `"i3bar"` -- in section `general` in `~/.config/i3status/config` add `output_format = "i3bar"`. It should look as follows.

    ```config
    general {
        output_format = "i3bar"
    }
    ```

3. In `~/.config/i3/config` set the bar status command to `i3status-wrapper` -- in section `bar` in `~/.config/i3/config` add `status_command i3status-wrapper`. It should look as follows.

    ```config
    bar {
        status_command i3status-wrapper
    }
    ```

## Configuration

Configuration is contained in `i3status-wrapper` file.

### Displayed blocks

In `i3status-wrapper` function `process_blocks` takes as an input the (parsed) output of `i3status` and return the list of blocks as described in [i3bar protocol](https://i3wm.org/docs/i3bar-protocol.html). This list will be displayed on `i3bar`.

### Click events

If block with `name` `"name"` was clicked, then function `BUTTONS["name"]` (defined in `i3status-wrapper`) will be executed. Such function is given the parameters described in [click events](https://i3wm.org/docs/i3bar-protocol.html#_click_events) section of the definition of [i3bar protocol](https://i3wm.org/docs/i3bar-protocol.html).

# cam_recorder

Stream IP cameras as ROS2 topics with optional rosbag recording and replay.

## Setup

This project uses [pixi](https://pixi.sh) for package management. It handles installing Python, ROS2, and all dependencies in an isolated environment — no system-level ROS2 installation required.

1. Install pixi: https://pixi.sh/latest/#installation
2. Install project dependencies:

```bash
pixi install
```

## Configuration

Copy the example config and fill in your camera credentials:

```bash
cp config/config.yaml.example config/config.yaml
```

Edit `config/config.yaml` with your camera names, RTSP URLs, desired FPS, and topic template. See the comments in the file for details.

## Tasks

| Task               | Description                                  | Usage                                      |
| ------------------ | -------------------------------------------- | ------------------------------------------ |
| `broadcast`        | Publish camera streams as ROS2 Image topics  | `pixi run broadcast`                       |
| `replay`           | Replay a rosbag supplied directly on the CLI | `pixi run replay <bag_path>`               |
| `replay_formatted` | Replay the rosbag configured for a scenario  | `pixi run replay_formatted --scenario 1_0` |
| `view`             | Display live camera topics in OpenCV windows | `pixi run view`                            |
| `test`             | Run the test suite                           | `pixi run test`                            |

### broadcast

Starts a ROS2 node that captures RTSP streams and publishes them as `sensor_msgs/msg/Image` on `/camera/<name>/image_raw` topics.

```bash
# Use default cameras
pixi run broadcast

# Record to rosbag while broadcasting
pixi run broadcast --collect-bag

# Custom camera and FPS
pixi run broadcast --camera cam0=rtsp://user:pass@host:554/stream --fps 10

# Specify bag output path
pixi run broadcast --collect-bag --bag-path ./bags/my_recording
```

### replay

Replays a rosbag and displays the images in OpenCV windows with timestamps overlaid.

```bash
pixi run replay bags/recording_20260312_120000

# Loop playback
pixi run replay bags/recording_20260312_120000 --loop

# Adjust playback speed
pixi run replay bags/recording_20260312_120000 --rate 2.0

# Replay without display
pixi run replay bags/recording_20260312_120000 --no-display
```

### view

Subscribes to camera image topics and displays them in OpenCV windows with timestamps.

```bash
# View default camera topics
pixi run view

# View specific topics
pixi run view --topic /camera/cam0/image_raw --topic /camera/cam1/image_raw
```

## macOS support

Apple Silicon macOS (`osx-arm64`) is supported through Pixi. Pixi installs the
project's Python, ROS 2 Kilted, MCAP, OpenCV, and CycloneDDS dependencies in an
isolated environment, so a separate system ROS 2 installation is not required.

The repository includes `config/cyclonedds-macos.xml`, which uses automatic
network-interface detection. `pixi.toml` activates it through
`CYCLONEDDS_URI`; this avoids errors caused by Linux-specific network interface
names on macOS.

### Install on macOS

Install Pixi using either the official installer:

```bash
curl -fsSL https://pixi.sh/install.sh | sh
source ~/.zshrc
```

or Homebrew:

```bash
brew install pixi
```

Then clone the repository and install its environment:

```bash
git clone https://github.com/rashidrao-pk/distrimuse-image-broadcaster.git
cd distrimuse-image-broadcaster
pixi install
```

Verify that the environment and ROS 2 are available:

```bash
pixi info
pixi run ros2 --help
```

For replay that only needs to communicate on the local computer, optionally
set:

```bash
export ROS_LOCALHOST_ONLY=1
```

Do not set this variable when ROS nodes on other computers need to discover the
replayed topics.

## Replay an existing rosbag by scenario

The new `replay_formatted` task selects the MCAP file from
`config/cf_mac.yaml`. After receiving or recording a rosbag, edit that file:

```yaml
data:
  masks:
  dataset_base: /path/to/dataset
  rosbag_basepath: /path/to/rosbag-directory
  rosbag_path: /path/to/rosbag-directory/recording_0.mcap
  mask_types:
    - PLeft
    - PRight
    - ConveBelt

scenario:
  id: "1_0"

playback_options:
  loop: true
```

Make sure that `data.rosbag_path` points to an existing `.mcap` file and that
the command's scenario matches `scenario.id`. Then run:

```bash
pixi run replay_formatted --scenario 1_0
```

The following command-line options override the YAML playback settings:

```bash
# Force looping
pixi run replay_formatted --scenario 1_0 --loop

# Disable looping even when loop: true is configured
pixi run replay_formatted --scenario 1_0 --no-loop

# Replay at twice the recorded speed
pixi run replay_formatted --scenario 1_0 --rate 2.0

# Replay without opening the OpenCV viewer
pixi run replay_formatted --scenario 1_0 --no-display

# Use a different replay configuration
pixi run replay_formatted --scenario 1_0 --config /path/to/replay.yaml
```

`--scenatio` is retained as an alias for compatibility, but `--scenario` is the
preferred spelling.

To bypass the scenario configuration and replay an MCAP file directly, use the
original task:

```bash
pixi run replay /path/to/recording_0.mcap --loop
```

Press `Ctrl+C` to stop playback.

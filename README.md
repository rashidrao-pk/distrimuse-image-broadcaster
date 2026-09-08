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

| Task                | Description                                  | Usage                                      |
| ------------------- | -------------------------------------------- | ------------------------------------------ |
| `broadcast`         | Publish camera streams as ROS2 Image topics  | `pixi run broadcast`                       |
| `inspect-rosbag`    | Inspect topics and sample frame information  | `pixi run inspect-rosbag`                  |
| `replay`            | Replay a rosbag supplied directly on the CLI | `pixi run replay <bag_path>`               |
| `replay_formatted`  | Replay the rosbag configured for a scenario  | `pixi run replay_formatted --scenario 1_0` |
| `summarize-dataset` | Write a CSV summary of all dataset rosbags   | `pixi run summarize-dataset`               |
| `view`              | Display live camera topics in OpenCV windows | `pixi run view`                            |
| `test`              | Run the test suite                           | `pixi run test`                            |

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

The `scenario_options` mapping in `config/cf_mac.yaml` contains one key and
rosbag path per recording. Paths may be absolute or relative to
`data.dataset_base`. Select any configured key when running the preview:

```bash
pixi run replay_formatted --scenario 1_0 --camera back_view \
```

For example, to preview scenario ID 8, sub-ID 4:

```bash
pixi run replay_formatted --scenario 8_4 --loop
```

The following command-line options override the YAML playback settings:

```bash
# Force looping
pixi run replay_formatted --scenario 1_0 --camera back_view --loop

# Disable looping even when loop: true is configured
pixi run replay_formatted --scenario 1_0 --no-loop

# Replay at twice the recorded speed
pixi run replay_formatted --scenario 1_0 --rate 2.0

# Replay without opening the OpenCV viewer
pixi run replay_formatted --scenario 1_0 --no-display

# Publish only the back camera (also the default in cf_mac.yaml)
pixi run replay_formatted --scenario 2_0 --camera back_view --loop

# Publish only the front camera
pixi run replay_formatted --scenario 2_0 --camera front_view --loop

# Publish both camera topics
pixi run replay_formatted --scenario 2_0 --camera both --loop

# Use a different replay configuration
pixi run replay_formatted --scenario 1_0 --config /path/to/replay.yaml
```

`--scenario` is retained as an alias for compatibility, but `--scenario` is the
preferred spelling.

To bypass the scenario configuration and replay an MCAP file directly, use the
original task:

```bash
pixi run replay /path/to/recording_0.mcap --loop
```

Press `Ctrl+C` to stop playback.

## Check All scenarios:

```bash
pixi run replay_formatted --scenario 1_0

pixi run replay_formatted --scenario 2_0

pixi run replay_formatted --scenario 3_0

pixi run replay_formatted --scenario 2_0

pixi run replay_formatted --scenario 2_0

pixi run replay_formatted --scenario 2_0

pixi run replay_formatted --scenario 2_0

```

## Inspect rosbag contents

Inspect the rosbag selected by `config/cf_mac.yaml` without replaying it:

```bash
pixi run inspect-rosbag
```

Inspect a configured scenario and save one sample from each camera under
`output/inspect_rosbag/1_0/`:

```bash
pixi run inspect-rosbag --scenario 1_0
```

The report includes bag size and duration, topic names and types, message
counts, recorded field definitions, and a sample from every topic. Image
samples also show their bag and ROS timestamps, frame ID, compression format,
dimensions, channels, and payload size.

Useful options:

```bash
# Inspect a rosbag supplied directly
pixi run inspect-rosbag /path/to/recording_0.mcap

# Inspect three frames from one camera
pixi run inspect-rosbag \
  --topic /camera/front_view/image_raw \
  --frames 3

# Use another configuration
pixi run inspect-rosbag --scenario 1_0 --config /path/to/replay.yaml

# Save three samples per image topic in a custom folder
pixi run inspect-rosbag --scenario 1_0 --frames 3 --output-dir ./output

# Print the report without saving sample images
pixi run inspect-rosbag --scenario 1_0 --no-save-frames
```

## Summarize a complete dataset

Recursively inspect every `.mcap` file below `data.dataset_base` in
`config/cf_mac.yaml` and create `dataset_summary.csv` in the project root:

```bash
pixi run summarize-dataset
```

Scenario ID, sub-ID, and recording date/time are extracted from names such as
`Jul27_Scenario_8_4_2026-07-27_12-01-36_0.mcap`. Each CSV row also contains bag
size, duration, start/end times, total messages, front/back frame counts and
FPS, robot-state count, topics, ROS distribution, paths, and inspection errors.

To select the dataset or output explicitly:

```bash
pixi run summarize-dataset /path/to/dataset --output /path/to/summary.csv
```

# 👥 Contributing

We welcome contributions! Check out our [Contributing Guide](CONTRIBUTING.md) to get started.

<p align="center">
  <a href="https://github.com/rashidrao-pk/distrimuse-image-broadcaster/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=rashidrao-pk/distrimuse-image-broadcaster" alt="Contributors to distrimuse-image-broadcaster" />
  </a>
</p>

<p align="center">
  <b>Thank you to all our contributors!</b>
</p>

"""Inspect rosbag metadata and sample messages without replaying the bag."""

import argparse
from datetime import datetime
from pathlib import Path
import sys

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CompressedImage, Image
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "cf_mac.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "inspect_rosbag"
IMAGE_TYPES = {
    "sensor_msgs/msg/CompressedImage": CompressedImage,
    "sensor_msgs/msg/Image": Image,
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Show rosbag metadata and information from sample frames"
    )
    parser.add_argument(
        "bag_path",
        nargs="?",
        type=Path,
        help="MCAP file or rosbag directory (defaults to data.rosbag_path)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Config used when bag_path is omitted (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--scenario",
        "--scenario",
        dest="scenario",
        help="Scenario key from scenario_options (for example: 1_0)",
    )
    parser.add_argument(
        "--topic",
        action="append",
        help="Only sample this topic; repeat to select multiple topics",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=1,
        help="Number of messages to inspect per selected topic (default: 1)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Base folder for saved sample frames (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-save-frames",
        action="store_true",
        help="Inspect messages without saving image samples",
    )
    return parser.parse_args(argv)


def resolve_bag_path(
    bag_path: Path | None, config_path: Path, scenario: str | None = None
) -> Path:
    if bag_path is None:
        if not config_path.is_file():
            raise ValueError(f"Config file does not exist: {config_path}")
        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
        data = config.get("data", {})
        if scenario:
            scenario_options = config.get("scenario_options") or config.get(
                "scanario_options"
            )
            if not isinstance(scenario_options, dict) or scenario not in scenario_options:
                available = ", ".join(sorted(scenario_options or {}))
                raise ValueError(
                    f"Unknown scenario key {scenario!r}. Available: {available}"
                )
            configured_path = scenario_options[scenario].get("rosbag_path")
        else:
            configured_path = data.get("rosbag_path")
        if not configured_path:
            raise ValueError("The selected config entry must define rosbag_path")
        bag_path = Path(configured_path).expanduser()
        if not bag_path.is_absolute():
            base_path = Path(data.get("dataset_base", config_path.parent)).expanduser()
            bag_path = base_path / bag_path

    bag_path = bag_path.expanduser().resolve()
    if not bag_path.exists():
        raise ValueError(f"Rosbag does not exist: {bag_path}")
    return bag_path


def format_time(timestamp_ns: int) -> str:
    seconds = timestamp_ns / 1_000_000_000
    local_time = datetime.fromtimestamp(seconds).astimezone()
    return f"{local_time.isoformat(timespec='microseconds')} ({timestamp_ns} ns)"


def format_duration(duration_ns: int) -> str:
    return f"{duration_ns / 1_000_000_000:.3f} seconds"


def extract_top_level_fields(message_definition: str) -> list[str]:
    """Return field declarations before nested MSG definitions."""
    fields = []
    for line in message_definition.splitlines():
        stripped = line.strip()
        if stripped.startswith("=") or stripped.startswith("MSG:"):
            break
        declaration = stripped.split("#", maxsplit=1)[0].strip()
        if declaration and not declaration.startswith("#"):
            fields.append(declaration)
    return fields


def header_fields(message) -> list[tuple[str, str]]:
    if not hasattr(message, "header"):
        return []
    stamp = message.header.stamp
    stamp_ns = stamp.sec * 1_000_000_000 + stamp.nanosec
    return [
        ("ROS header timestamp", format_time(stamp_ns)),
        ("Frame ID", message.header.frame_id or "<empty>"),
    ]


def inspect_image(serialized_data: bytes, message_type: str):
    message = deserialize_message(serialized_data, IMAGE_TYPES[message_type])
    details = header_fields(message)

    if isinstance(message, CompressedImage):
        encoded = np.frombuffer(message.data, dtype=np.uint8)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
        dimensions = (
            f"{decoded.shape[1]} x {decoded.shape[0]}"
            if decoded is not None
            else "<could not decode>"
        )
        channels = (
            1 if decoded is not None and decoded.ndim == 2
            else decoded.shape[2] if decoded is not None else "<unknown>"
        )
        details.extend(
            [
                ("Image format", message.format or "<empty>"),
                ("Decoded dimensions", dimensions),
                ("Decoded channels", str(channels)),
                ("Compressed payload", f"{len(message.data):,} bytes"),
            ]
        )
    else:
        details.extend(
            [
                ("Dimensions", f"{message.width} x {message.height}"),
                ("Encoding", message.encoding or "<empty>"),
                ("Row step", f"{message.step:,} bytes"),
                ("Image payload", f"{len(message.data):,} bytes"),
            ]
        )
    return details, decoded if isinstance(message, CompressedImage) else None


def open_reader(bag_path: Path):
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="",
            output_serialization_format="",
        ),
    )
    return reader


def sample_filename(topic: str, sample_number: int) -> str:
    camera_name = topic.removeprefix("/camera/").removesuffix("/image_raw")
    safe_name = camera_name.strip("/").replace("/", "_")
    return f"{safe_name}_sample_{sample_number:03d}.png"


def inspect_bag(
    bag_path: Path,
    selected_topics=None,
    frames_per_topic=1,
    output_dir: Path | None = None,
):
    if frames_per_topic < 1:
        raise ValueError("--frames must be at least 1")

    reader = open_reader(bag_path)
    metadata = reader.get_metadata()
    definitions = {
        definition.topic_type: extract_top_level_fields(
            definition.encoded_message_definition
        )
        for definition in reader.get_all_message_definitions()
    }
    topic_types = {
        item.topic_metadata.name: item.topic_metadata.type
        for item in metadata.topics_with_message_count
    }
    available_topics = set(topic_types)
    requested_topics = set(selected_topics or available_topics)
    unknown_topics = requested_topics - available_topics
    if unknown_topics:
        raise ValueError(
            "Topic(s) not found: " + ", ".join(sorted(unknown_topics))
        )

    print("Rosbag")
    print(f"  Path: {bag_path}")
    print(f"  Storage: {metadata.storage_identifier}")
    print(f"  ROS distribution: {metadata.ros_distro or '<unknown>'}")
    print(f"  Size: {metadata.bag_size:,} bytes")
    print(f"  Start: {format_time(metadata.starting_time.nanoseconds)}")
    print(f"  Duration: {format_duration(metadata.duration.nanoseconds)}")
    print(f"  Messages: {metadata.message_count:,}")
    print("\nTopics")
    for item in metadata.topics_with_message_count:
        topic = item.topic_metadata
        print(f"  {topic.name}")
        print(f"    Type: {topic.type}")
        print(f"    Serialization: {topic.serialization_format}")
        print(f"    Messages: {item.message_count:,}")
        if definitions.get(topic.type):
            print("    Recorded fields:")
            for field in definitions[topic.type]:
                print(f"      - {field}")

    print("\nSample messages")
    inspected = {topic: 0 for topic in requested_topics}
    while reader.has_next() and any(
        count < frames_per_topic for count in inspected.values()
    ):
        topic, serialized_data, timestamp_ns = reader.read_next()
        if topic not in inspected or inspected[topic] >= frames_per_topic:
            continue

        inspected[topic] += 1
        message_type = topic_types[topic]
        print(f"  {topic} — sample {inspected[topic]}")
        print(f"    Type: {message_type}")
        print(f"    Bag timestamp: {format_time(timestamp_ns)}")
        print(f"    Serialized message: {len(serialized_data):,} bytes")

        if message_type in IMAGE_TYPES:
            details, decoded_image = inspect_image(serialized_data, message_type)
            for label, value in details:
                print(f"    {label}: {value}")
            if output_dir is not None and decoded_image is not None:
                output_dir.mkdir(parents=True, exist_ok=True)
                frame_path = output_dir / sample_filename(topic, inspected[topic])
                if not cv2.imwrite(str(frame_path), decoded_image):
                    raise RuntimeError(f"Could not save sample frame: {frame_path}")
                print(f"    Saved frame: {frame_path}")
        else:
            print(
                "    Fields: not decoded (the custom ROS message package "
                "may be required)"
            )


def main(argv=None):
    args = parse_args(argv)
    try:
        bag_path = resolve_bag_path(args.bag_path, args.config, args.scenario)
        output_key = args.scenario or bag_path.stem
        output_dir = None if args.no_save_frames else args.output_dir / output_key
        inspect_bag(bag_path, args.topic, args.frames, output_dir)
    except (OSError, RuntimeError, TypeError, ValueError, yaml.YAMLError) as error:
        print(f"inspect-rosbag: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

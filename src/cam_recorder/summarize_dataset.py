"""Create a CSV summary for every MCAP rosbag in a dataset."""

import argparse
import csv
from datetime import datetime
from pathlib import Path
import re
import sys

import rosbag2_py
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "cf_mac.yaml"
DEFAULT_OUTPUT = PROJECT_ROOT / "dataset_summary.csv"
NAME_PATTERN = re.compile(
    r"Scenario_(?P<scenario_id>\d+)_(?P<sub_id>\d+)_"
    r"(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{2}-\d{2}-\d{2})"
)
CORE_COLUMNS = [
    "scenario_id",
    "sub_id",
    "scenario_key",
    "recording_datetime",
    "bag_name",
    "relative_path",
    "size_bytes",
    "size_gib",
    "duration_seconds",
    "start_time",
    "end_time",
    "total_messages",
    "front_frames",
    "back_frames",
    "robot_state_messages",
    "front_fps",
    "back_fps",
    "topic_count",
    "topics",
    "storage_id",
    "ros_distro",
    "error",
]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Summarize all MCAP rosbags under a dataset as CSV"
    )
    parser.add_argument(
        "dataset_base",
        nargs="?",
        type=Path,
        help="Dataset directory (defaults to data.dataset_base in config)",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def resolve_dataset_base(dataset_base: Path | None, config_path: Path) -> Path:
    if dataset_base is None:
        if not config_path.is_file():
            raise ValueError(f"Config file does not exist: {config_path}")
        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
        configured_base = config.get("data", {}).get("dataset_base")
        if not configured_base:
            raise ValueError("Config must define data.dataset_base")
        dataset_base = Path(configured_base).expanduser()
        if not dataset_base.is_absolute():
            dataset_base = config_path.parent / dataset_base

    dataset_base = dataset_base.expanduser().resolve()
    if not dataset_base.is_dir():
        raise ValueError(f"Dataset directory does not exist: {dataset_base}")
    return dataset_base


def parse_bag_name(path: Path) -> dict[str, str]:
    match = NAME_PATTERN.search(path.stem) or NAME_PATTERN.search(path.parent.name)
    if not match:
        return {
            "scenario_id": "",
            "sub_id": "",
            "scenario_key": "",
            "recording_datetime": "",
        }

    values = match.groupdict()
    recorded = datetime.strptime(
        f"{values['date']} {values['time']}", "%Y-%m-%d %H-%M-%S"
    )
    return {
        "scenario_id": values["scenario_id"],
        "sub_id": values["sub_id"],
        "scenario_key": f"{values['scenario_id']}_{values['sub_id']}",
        "recording_datetime": recorded.isoformat(),
    }


def iso_time(timestamp_ns: int) -> str:
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000).astimezone().isoformat()


def read_metadata(bag_path: Path):
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="", output_serialization_format=""
        ),
    )
    return reader.get_metadata()


def summarize_bag(bag_path: Path, dataset_base: Path) -> dict[str, object]:
    row: dict[str, object] = {
        **parse_bag_name(bag_path),
        "bag_name": bag_path.name,
        "relative_path": str(bag_path.relative_to(dataset_base)),
        "error": "",
    }
    try:
        metadata = read_metadata(bag_path)
        duration = metadata.duration.nanoseconds / 1_000_000_000
        start_ns = metadata.starting_time.nanoseconds
        topic_counts = {
            item.topic_metadata.name: item.message_count
            for item in metadata.topics_with_message_count
        }
        front_frames = topic_counts.get("/camera/front_view/image_raw", 0)
        back_frames = topic_counts.get("/camera/back_view/image_raw", 0)
        row.update(
            {
                "size_bytes": metadata.bag_size,
                "size_gib": f"{metadata.bag_size / (1024 ** 3):.3f}",
                "duration_seconds": f"{duration:.3f}",
                "start_time": iso_time(start_ns),
                "end_time": iso_time(start_ns + metadata.duration.nanoseconds),
                "total_messages": metadata.message_count,
                "front_frames": front_frames,
                "back_frames": back_frames,
                "robot_state_messages": topic_counts.get("/sr/state", 0),
                "front_fps": f"{front_frames / duration:.3f}" if duration else "",
                "back_fps": f"{back_frames / duration:.3f}" if duration else "",
                "topic_count": len(topic_counts),
                "topics": "; ".join(
                    f"{name} ({count})" for name, count in sorted(topic_counts.items())
                ),
                "storage_id": metadata.storage_identifier,
                "ros_distro": metadata.ros_distro,
            }
        )
    except Exception as error:  # Keep broken bags visible in the dataset report.
        row["error"] = str(error)
    return row


def natural_sort_key(path: Path):
    parsed = parse_bag_name(path)
    if parsed["scenario_id"]:
        return (int(parsed["scenario_id"]), int(parsed["sub_id"]), path.name)
    return (sys.maxsize, sys.maxsize, path.name)


def summarize_dataset(dataset_base: Path, output_path: Path) -> list[dict]:
    bag_paths = sorted(dataset_base.rglob("*.mcap"), key=natural_sort_key)
    if not bag_paths:
        raise ValueError(f"No .mcap files found under: {dataset_base}")

    rows = []
    for index, bag_path in enumerate(bag_paths, start=1):
        print(f"[{index}/{len(bag_paths)}] {bag_path.name}")
        rows.append(summarize_bag(bag_path, dataset_base))

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CORE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv=None):
    args = parse_args(argv)
    try:
        dataset_base = resolve_dataset_base(args.dataset_base, args.config)
        rows = summarize_dataset(dataset_base, args.output)
    except (OSError, RuntimeError, TypeError, ValueError, yaml.YAMLError) as error:
        print(f"summarize-dataset: error: {error}", file=sys.stderr)
        return 2

    errors = sum(bool(row["error"]) for row in rows)
    scenarios = len({row["scenario_id"] for row in rows if row["scenario_id"]})
    print(f"\nWrote {len(rows)} bags across {scenarios} scenario IDs to {args.output}")
    if errors:
        print(f"Warning: {errors} bag(s) could not be fully inspected")
    return 0


if __name__ == "__main__":
    sys.exit(main())

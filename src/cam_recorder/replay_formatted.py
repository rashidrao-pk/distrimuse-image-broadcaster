"""Replay a configured rosbag with the camera viewer."""

import argparse
from pathlib import Path
import subprocess
import sys
import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor
import yaml

from cam_recorder.replay import get_bag_image_topics
from cam_recorder.viewer import CameraViewerNode


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "cf_mac.yaml"


def load_replay_config(config_path: Path) -> dict:
    """Load and minimally validate a replay configuration."""
    if not config_path.is_file():
        raise ValueError(f"Config file does not exist: {config_path}")

    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    data = config.get("data")
    scenario = config.get("scenario")
    if not isinstance(data, dict) or not data.get("rosbag_path"):
        raise ValueError("Config must define data.rosbag_path")
    if not isinstance(scenario, dict) or scenario.get("id") is None:
        raise ValueError("Config must define scenario.id")

    return config


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Replay the rosbag selected in config/cf_mac.yaml"
    )
    parser.add_argument(
        "--scenario",
        "--scenatio",
        dest="scenario",
        required=True,
        help="Scenario ID to replay (for example: 1_0)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Replay config file (default: {DEFAULT_CONFIG})",
    )
    loop_group = parser.add_mutually_exclusive_group()
    loop_group.add_argument(
        "--loop",
        dest="loop",
        action="store_true",
        default=None,
        help="Loop playback (overrides the config)",
    )
    loop_group.add_argument(
        "--no-loop",
        dest="loop",
        action="store_false",
        help="Do not loop playback (overrides the config)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Playback rate (overrides playback_options.rate)",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Play without the camera viewer",
    )
    return parser.parse_args(argv)


def resolve_options(args, config):
    configured_scenario = str(config["scenario"]["id"])
    if args.scenario != configured_scenario:
        raise ValueError(
            f"Scenario {args.scenario!r} does not match configured scenario "
            f"{configured_scenario!r} in {args.config}"
        )

    bag_path = Path(config["data"]["rosbag_path"]).expanduser()
    if not bag_path.is_absolute():
        bag_path = (args.config.parent / bag_path).resolve()
    if not bag_path.exists():
        raise ValueError(f"Configured rosbag does not exist: {bag_path}")

    playback = config.get("playback_options") or {}
    loop = args.loop if args.loop is not None else bool(playback.get("loop", False))
    rate = args.rate if args.rate is not None else float(playback.get("rate", 1.0))
    if rate <= 0:
        raise ValueError("Playback rate must be greater than zero")
    return bag_path, loop, rate


def play(bag_path: Path, loop: bool, rate: float, no_display: bool) -> int:
    cmd = ["ros2", "bag", "play", str(bag_path)]
    if loop:
        cmd.append("--loop")
    if rate != 1.0:
        cmd.extend(["--rate", str(rate)])

    print(f"Replaying: {bag_path}")
    print(f"Command: {' '.join(cmd)}")

    if no_display:
        return subprocess.call(cmd)

    topics = get_bag_image_topics(str(bag_path))
    if not topics:
        print("No compressed-image topics found; playing without display.")
        return subprocess.call(cmd)

    bag_proc = subprocess.Popen(cmd)
    rclpy.init()
    node = CameraViewerNode(topics)
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        while bag_proc.poll() is None:
            node.display_once()
    except KeyboardInterrupt:
        bag_proc.terminate()
    finally:
        executor.shutdown()
        spin_thread.join(timeout=2)
        node.shutdown()
        node.destroy_node()
        rclpy.shutdown()
        bag_proc.wait()

    return bag_proc.returncode


def main(argv=None):
    args = parse_args(argv)
    try:
        config = load_replay_config(args.config)
        bag_path, loop, rate = resolve_options(args, config)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
        print(f"replay: error: {error}", file=sys.stderr)
        return 2

    return play(bag_path, loop, rate, args.no_display)


if __name__ == "__main__":
    sys.exit(main())

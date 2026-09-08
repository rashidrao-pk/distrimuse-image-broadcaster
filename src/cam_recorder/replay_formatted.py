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
CAMERA_TOPICS = {
    "back_view": "/camera/back_view/image_raw",
    "front_view": "/camera/front_view/image_raw",
}


def load_replay_config(config_path: Path) -> dict:
    """Load and minimally validate a replay configuration."""
    if not config_path.is_file():
        raise ValueError(f"Config file does not exist: {config_path}")

    with config_path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    data = config.get("data")
    scenario_options = config.get("scenario_options") or config.get(
        "scanario_options"
    )
    if not isinstance(data, dict):
        raise ValueError("Config must define data")
    if not data.get("rosbag_path") and not isinstance(scenario_options, dict):
        raise ValueError("Config must define data.rosbag_path or scenario_options")

    return config


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Replay the rosbag selected in config/cf_mac.yaml"
    )
    parser.add_argument(
        "--scenario",
        "--scenario",  # --- IGNORE ---
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
        "--camera",
        choices=("back_view", "front_view", "both"),
        default=None,
        help="Camera topic(s) to publish (default: playback_options.camera)",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Play without the camera viewer",
    )
    return parser.parse_args(argv)


def resolve_options(args, config):
    scenario_options = config.get("scenario_options") or config.get(
        "scanario_options"
    )
    if isinstance(scenario_options, dict):
        scenario_config = scenario_options.get(args.scenario)
        if not isinstance(scenario_config, dict):
            available = ", ".join(sorted(scenario_options))
            raise ValueError(
                f"Unknown scenario key {args.scenario!r}. Available: {available}"
            )
        configured_path = scenario_config.get("rosbag_path")
        if not configured_path:
            raise ValueError(
                f"scenario_options.{args.scenario}.rosbag_path is required"
            )
    else:
        configured_scenario = str(config.get("scenario", {}).get("id", ""))
        if args.scenario != configured_scenario:
            raise ValueError(
                f"Scenario {args.scenario!r} does not match configured scenario "
                f"{configured_scenario!r} in {args.config}"
            )
        configured_path = config["data"]["rosbag_path"]

    bag_path = Path(configured_path).expanduser()
    if not bag_path.is_absolute():
        dataset_base = Path(config["data"].get("dataset_base", args.config.parent))
        bag_path = (dataset_base.expanduser() / bag_path).resolve()
    if not bag_path.exists():
        raise ValueError(f"Configured rosbag does not exist: {bag_path}")

    playback = config.get("playback_options") or {}
    loop = args.loop if args.loop is not None else bool(playback.get("loop", False))
    rate = args.rate if args.rate is not None else float(playback.get("rate", 1.0))
    if rate <= 0:
        raise ValueError("Playback rate must be greater than zero")
    return bag_path, loop, rate


def resolve_camera(args, config) -> str:
    playback = config.get("playback_options") or {}
    camera = args.camera or playback.get("camera", "back_view")
    if camera not in {"back_view", "front_view", "both"}:
        raise ValueError(
            "Camera must be one of: back_view, front_view, both"
        )
    return camera


def select_camera_topics(bag_topics: list[str], camera: str) -> list[str]:
    requested = (
        list(CAMERA_TOPICS.values())
        if camera == "both"
        else [CAMERA_TOPICS[camera]]
    )
    selected = [topic for topic in requested if topic in bag_topics]
    missing = [topic for topic in requested if topic not in bag_topics]
    if missing:
        raise ValueError(
            "Requested camera topic(s) not found in bag: " + ", ".join(missing)
        )
    return selected


def build_play_command(
    bag_path: Path, loop: bool, rate: float, topics: list[str]
) -> list[str]:
    cmd = ["ros2", "bag", "play", str(bag_path)]
    if loop:
        cmd.append("--loop")
    if rate != 1.0:
        cmd.extend(["--rate", str(rate)])
    cmd.extend(["--topics", *topics])
    return cmd


def play(
    bag_path: Path, loop: bool, rate: float, camera: str, no_display: bool
) -> int:
    bag_topics = get_bag_image_topics(str(bag_path))
    topics = select_camera_topics(bag_topics, camera)
    cmd = build_play_command(bag_path, loop, rate, topics)

    print(f"Replaying: {bag_path}")
    print(f"Camera selection: {camera}")
    print(f"Command: {' '.join(cmd)}")

    if no_display:
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
        camera = resolve_camera(args, config)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
        print(f"replay: error: {error}", file=sys.stderr)
        return 2

    return play(bag_path, loop, rate, camera, args.no_display)


if __name__ == "__main__":
    sys.exit(main())

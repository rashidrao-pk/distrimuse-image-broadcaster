from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from cam_recorder.replay_formatted import (
    build_play_command,
    load_replay_config,
    parse_args,
    resolve_camera,
    resolve_options,
    select_camera_topics,
)


def test_default_command_accepts_scenario_and_loop():
    args = parse_args(["--scenario", "1_0", "--loop"])

    assert args.scenario == "1_0"
    assert args.loop is True



def test_documented_scenario_alias_is_supported():
    args = parse_args(["--scenario", "1_0"])

    assert args.scenario == "1_0"


def test_camera_defaults_to_configured_back_view():
    args = parse_args(["--scenario", "1_0"])

    assert resolve_camera(args, {"playback_options": {"camera": "back_view"}}) == (
        "back_view"
    )


def test_both_selects_front_and_back_topics():
    bag_topics = [
        "/camera/front_view/image_raw",
        "/camera/back_view/image_raw",
    ]

    assert select_camera_topics(bag_topics, "both") == [
        "/camera/back_view/image_raw",
        "/camera/front_view/image_raw",
    ]


def test_play_command_filters_to_selected_topics(tmp_path):
    command = build_play_command(
        tmp_path / "bag.mcap",
        loop=True,
        rate=1.0,
        topics=["/camera/back_view/image_raw"],
    )

    assert command[-2:] == ["--topics", "/camera/back_view/image_raw"]
    assert "--loop" in command


def test_config_values_are_resolved(tmp_path):
    bag_path = tmp_path / "recording.mcap"
    bag_path.touch()
    config_path = tmp_path / "replay.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "data": {"rosbag_path": str(bag_path)},
                "scenario": {"id": "1_0"},
                "playback_options": {"loop": True, "rate": 0.5},
            }
        ),
        encoding="utf-8",
    )
    args = Namespace(
        scenario="1_0", config=config_path, loop=None, rate=None
    )

    config = load_replay_config(config_path)
    assert resolve_options(args, config) == (bag_path, True, 0.5)


def test_scenario_must_match_config(tmp_path):
    bag_path = tmp_path / "recording.mcap"
    bag_path.touch()
    args = Namespace(
        scenario="2_0",
        config=tmp_path / "replay.yaml",
        loop=None,
        rate=None,
    )
    config = {
        "data": {"rosbag_path": str(bag_path)},
        "scenario": {"id": "1_0"},
    }

    with pytest.raises(ValueError, match="does not match"):
        resolve_options(args, config)


def test_scenario_key_selects_path_from_options(tmp_path):
    bag_path = tmp_path / "scenario_8_4.mcap"
    bag_path.touch()
    args = Namespace(
        scenario="8_4", config=tmp_path / "replay.yaml", loop=None, rate=None
    )
    config = {
        "data": {"dataset_base": str(tmp_path)},
        "scenario_options": {
            "8_4": {"rosbag_path": bag_path.name},
        },
    }

    assert resolve_options(args, config) == (bag_path, False, 1.0)

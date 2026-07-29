from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from cam_recorder.replay_formatted import load_replay_config, parse_args, resolve_options


def test_default_command_accepts_scenario_and_loop():
    args = parse_args(["--scenario", "1_0", "--loop"])

    assert args.scenario == "1_0"
    assert args.loop is True


def test_documented_scenatio_alias_is_supported():
    args = parse_args(["--scenatio", "1_0"])

    assert args.scenario == "1_0"


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

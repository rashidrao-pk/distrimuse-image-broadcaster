from pathlib import Path

import yaml

from cam_recorder.inspect_rosbag import (
    extract_top_level_fields,
    format_duration,
    parse_args,
    resolve_bag_path,
)


def test_parse_defaults_to_config():
    args = parse_args([])

    assert args.bag_path is None
    assert args.frames == 1


def test_resolve_bag_path_from_config(tmp_path):
    bag_path = tmp_path / "recording.mcap"
    bag_path.touch()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"data": {"rosbag_path": str(bag_path)}}),
        encoding="utf-8",
    )

    assert resolve_bag_path(None, config_path) == bag_path


def test_explicit_bag_path_does_not_require_config(tmp_path):
    bag_path = tmp_path / "recording.mcap"
    bag_path.touch()

    assert resolve_bag_path(bag_path, Path("missing.yaml")) == bag_path


def test_format_duration():
    assert format_duration(2_500_000_000) == "2.500 seconds"


def test_extract_top_level_fields_ignores_comments_and_nested_types():
    definition = """\
# state
bool enabled  # whether enabled
string[] names
=====
MSG: example/Nested
int8 value
"""

    assert extract_top_level_fields(definition) == [
        "bool enabled",
        "string[] names",
    ]
